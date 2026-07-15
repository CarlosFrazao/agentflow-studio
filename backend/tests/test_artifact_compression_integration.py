"""Testes de integração da Fase B1 — compressão no handoff researching->planning.

Cobre:
- `should_compress_artifact` (helper puro budget-aware no orchestrator).
- `maybe_compress` / `budget_remaining_usd` (helpers de pipeline_helpers,
  reutilizados por run.py e pelo Conductor F-023).
- Fluxo real: card em 'planning' consome o artifact 'research' comprimido antes
  de passar ao Planner. `compress_artifact` é sempre mockado (sem rede/LLM).
"""

import pytest

from app.services.orchestrator import should_compress_artifact

asyncio_test = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# should_compress_artifact (puro)
# ---------------------------------------------------------------------------

def test_should_compress_small_text_is_false() -> None:
    assert should_compress_artifact(
        "curto", threshold_chars=4000, budget_remaining_usd=5.0
    ) is False


def test_should_compress_large_text_within_budget_is_true() -> None:
    assert should_compress_artifact(
        "x" * 5000, threshold_chars=4000, budget_remaining_usd=5.0
    ) is True


def test_should_compress_respects_budget_cap() -> None:
    # Acima do threshold, mas sem orçamento restante -> não comprime (F-011).
    assert should_compress_artifact(
        "x" * 5000, threshold_chars=4000, budget_remaining_usd=0.0
    ) is False


def test_should_compress_none_budget_allows() -> None:
    assert should_compress_artifact(
        "x" * 5000, threshold_chars=4000, budget_remaining_usd=None
    ) is True


# ---------------------------------------------------------------------------
# _maybe_compress (run.py) — fail-open e respeito ao budget
# ---------------------------------------------------------------------------

@asyncio_test
async def test_maybe_compress_calls_compressor_when_eligible(monkeypatch) -> None:
    from app.services import pipeline_helpers as ph_mod

    called = {}

    async def _fake_compress(text: str, budget_tokens: int = 800) -> str:
        called["text_len"] = len(text)
        return "RESUMIDO"

    monkeypatch.setattr(ph_mod, "compress_artifact", _fake_compress)
    out = await ph_mod.maybe_compress("x" * 5000, budget_remaining_usd=5.0)
    assert out == "RESUMIDO"
    assert called["text_len"] == 5000


@asyncio_test
async def test_maybe_compress_skips_when_budget_exhausted(monkeypatch) -> None:
    from app.services import pipeline_helpers as ph_mod

    async def _fail(text: str, budget_tokens: int = 800) -> str:
        raise AssertionError("não deveria comprimir sem orçamento")

    monkeypatch.setattr(ph_mod, "compress_artifact", _fail)
    big = "x" * 5000
    out = await ph_mod.maybe_compress(big, budget_remaining_usd=0.0)
    assert out == big  # devolve original, sem chamar o compressor


@asyncio_test
async def test_maybe_compress_fail_open(monkeypatch) -> None:
    from app.services import pipeline_helpers as ph_mod

    async def _boom(text: str, budget_tokens: int = 800) -> str:
        raise RuntimeError("compressor quebrou")

    monkeypatch.setattr(ph_mod, "compress_artifact", _boom)
    big = "x" * 5000
    out = await ph_mod.maybe_compress(big, budget_remaining_usd=5.0)
    assert out == big  # fail-open: retorna original em vez de derrubar o pipeline


# ---------------------------------------------------------------------------
# Fluxo real via endpoint /run na etapa planning
# ---------------------------------------------------------------------------

async def _seed_card_in_planning(client) -> str:
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards",
        json={"project_id": pid, "title": "Ideia", "column": "planning"},
    )
    return card.json()["data"]["id"]


@asyncio_test
async def test_planning_run_compresses_research_artifact(client, monkeypatch) -> None:
    from app.services import pipeline_helpers as ph_mod
    from app.services.agents.planner import PlannerAgent, PlannerOutput

    big_report = (
        "## Concorrentes\n- Acme\n## Gaps de Mercado\n- CI nativo\n"
        + ("preenchimento " * 500)
    )

    compressed_calls: list[int] = []

    async def _fake_compress(text: str, budget_tokens: int = 800) -> str:
        compressed_calls.append(len(text))
        return "## Concorrentes\n- Acme\n## Gaps\n- CI"

    received: dict[str, str] = {}

    async def _fake_planner_run(self, ideation, research, code_research):
        received["research"] = research
        received["code_research"] = code_research
        return PlannerOutput(title="Plano", raw_plan="ok")

    monkeypatch.setattr(ph_mod, "compress_artifact", _fake_compress)
    monkeypatch.setattr(PlannerAgent, "run", _fake_planner_run)

    cid = await _seed_card_in_planning(client)
    # cria o artifact 'research' grande que o Planner deve consumir comprimido
    await client.post(
        f"/api/v1/cards/{cid}/artifacts",
        json={"agent_name": "research", "type": "markdown", "content": big_report},
    )

    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # o compressor foi chamado com o relatório grande
    assert compressed_calls and compressed_calls[0] == len(big_report)
    # o Planner recebeu a versão comprimida, não o original
    assert received["research"] == "## Concorrentes\n- Acme\n## Gaps\n- CI"
    assert len(received["research"]) < len(big_report)
