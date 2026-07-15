"""Testes TDD do Conductor (F-023) — Orquestração Conversacional.

Cobre (Plano F-023 §7):
1. run_ideation cria Card + Conversation.card_id preenchido.
2. run_research + run_code_research executam com asyncio.gather (timestamps
   sobrepostos provados via ordem de eventos concorrentes).
3. Reviewer critical -> Conductor responde com ask_user (não decide sozinho).
4. Limiar 0.85 reaproveitado de orchestrator (confiança alta -> auto_approve).
5. Card reflete as mesmas colunas que o /run produziria.
6. Pipeline completo por chat, do zero ao código, sem tocar o Kanban manualmente.

LLM/agents mockados; sra/firecrawl/github/sandbox injetados via override.
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Artifact, Conversation, Message
from app.models.conversation import MSG_ROLES
from app.sandbox.base import SandboxBackend, SandboxResult

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fakes de serviços externos (evitam rede/LLM reais)
# ---------------------------------------------------------------------------

class _DummySRA:
    async def research(self, query, mode="guerrilha"):
        raise RuntimeError("dummy sra: sem rede")


class _DummyFirecrawl:
    async def scrape(self, url):
        raise RuntimeError("dummy firecrawl: sem rede")


class _DummyGithub:
    async def search_repos(self, query, per_page=5):
        return []

    async def get_file(self, repo, path):
        return ""


class _OkSandbox(SandboxBackend):
    name = "ok"

    async def validate(self, code: str) -> SandboxResult:
        return SandboxResult(success=True, stderr="", backend=self.name)


class _FakeLLM:
    """LLM fake: devolve tool_calls vazio -> o Conductor usa o fallback
    determinístico por coluna (equivalente ao plano do LLM para os testes)."""

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {"narrative": "", "tool_calls": []}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return "narrativa fake"


def _override_services(client, llm) -> None:
    """Injeta fakes via request.app.state['service_overrides'] (ver deps.py)."""
    from app.services.deps import _STATE_KEY

    app = client._transport.app
    overrides = getattr(app.state, _STATE_KEY, {})
    overrides["llm"] = llm
    overrides["sra"] = _DummySRA()
    overrides["firecrawl"] = _DummyFirecrawl()
    overrides["github"] = _DummyGithub()
    overrides["sandbox"] = _OkSandbox()
    setattr(app.state, _STATE_KEY, overrides)


async def _seed_project(client) -> str:
    resp = await client.post("/api/v1/projects", json={"name": "P"})
    return resp.json()["data"]["id"]


async def _create_conversation(client, project_id: str) -> str:
    resp = await client.post(
        "/api/v1/conversations", json={"project_id": project_id}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _turn(client, conv_id: str, content: str) -> dict:
    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages", json={"content": content}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# 1) run_ideation cria Card + Conversation.card_id
# ---------------------------------------------------------------------------

async def test_run_ideation_creates_card_and_binds_conversation(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match", "rotas"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    body = await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    assert body["card_id"] is not None
    assert body["awaiting_user"] is False

    # O Card foi criado e avançou para researching (Ideation concluído).
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "researching"

    # Conversation.card_id foi preenchido.
    async with session_factory() as s:
        conv = await s.get(Conversation, UUID(cid))
        assert conv.card_id == UUID(body["card_id"])


# ---------------------------------------------------------------------------
# 2) research + code_research em paralelo (asyncio.gather)
# ---------------------------------------------------------------------------

async def test_research_and_code_research_run_in_parallel(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )

    # Registra a ordem de start/end para provar sobreposição real (gather).
    events: list[tuple[str, str]] = []

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        events.append(("research", "start"))
        await asyncio.sleep(0.02)
        events.append(("research", "end"))
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        events.append(("code_research", "start"))
        await asyncio.sleep(0.02)
        events.append(("code_research", "end"))
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    # T1: cria o card (ideation) -> researching.
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    # T2: pesquisa (research + code_research em paralelo).
    body = await _turn(client, cid, "seguir com a pesquisa")

    assert body["awaiting_user"] is False
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "planning"

    # Prova de paralelismo: ambos iniciaram ANTES de qualquer um terminar.
    assert events[0] == ("research", "start")
    assert events[1] == ("code_research", "start")
    assert ("research", "end") not in events[:2]
    assert ("code_research", "end") not in events[:2]


# ---------------------------------------------------------------------------
# 3) Reviewer critical -> Conductor pergunta ao usuário (ask_user)
# ---------------------------------------------------------------------------

async def test_reviewer_critical_makes_conductor_ask_user(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import (
        ReviewerAgent,
        ReviewOutput,
        ReviewAlert,
    )

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[ReviewAlert(message="risco critico", severity="critical")],
            critical_count=1,
            passed=False,
            confidence_score=0.4,
            log_summary="risco critico",
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "seguir com a pesquisa")
    await _turn(client, cid, "fazer o plano")
    body = await _turn(client, cid, "revisar")

    # O Conductor NÃO avança o card e sinaliza que aguarda o usuário.
    assert body["awaiting_user"] is True
    card = await client.get("/api/v1/cards/" + body["card_id"])
    # Card permanece em reviewing (não decide sozinho).
    assert card.json()["data"]["column"] == "reviewing"


# ---------------------------------------------------------------------------
# 4) Limiar 0.85 reaproveitado de orchestrator (confiança alta -> auto_approve)
# ---------------------------------------------------------------------------

async def test_auto_approve_threshold_reused_from_orchestrator(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput
    from app.services.orchestrator import (
        AUTO_APPROVE_CONFIDENCE_THRESHOLD,
        should_auto_approve,
    )

    # A constante vem do orchestrator (não duplicada no conductor).
    from app.services.conductor import AUTO_APPROVE_REVERT_WINDOW_MIN  # noqa: F401

    assert AUTO_APPROVE_CONFIDENCE_THRESHOLD == 0.85
    assert should_auto_approve(0.9, 0) is True
    assert should_auto_approve(0.84, 0) is False

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=True,
            confidence_score=0.95,
            log_summary=None,
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "seguir com a pesquisa")
    await _turn(client, cid, "fazer o plano")
    body = await _turn(client, cid, "revisar")

    card = await client.get("/api/v1/cards/" + body["card_id"])
    data = card.json()["data"]
    assert data["column"] == "done"
    assert data["auto_approved"] is True
    assert data["approval_by"] == "auto"


# ---------------------------------------------------------------------------
# 5) Card reflete as mesmas colunas que o /run produziria
# ---------------------------------------------------------------------------

async def test_card_columns_match_run_pipeline(
    client, session_factory, monkeypatch
) -> None:
    from app.models.card import KANBAN_COLUMNS
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    # Reviewer REPROVA (sem crítico) -> production (ciclo Criação<->Revisão).
    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=False,
            confidence_score=0.5,
            log_summary="reprovado",
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    # Cada mensagem avança o card exatamente como o /run faria.
    seq = [
        ("quero criar um app de caronas", "researching"),
        ("pesquisar", "planning"),
        ("planejar", "reviewing"),
        ("revisar", "production"),  # reviewer reprovou -> production
        ("gerar codigo", "done"),   # dev em production -> done
    ]
    for msg, expected_col in seq:
        body = await _turn(client, cid, msg)
        card = await client.get("/api/v1/cards/" + body["card_id"])
        assert card.json()["data"]["column"] == expected_col

    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] in KANBAN_COLUMNS


# ---------------------------------------------------------------------------
# 6) Pipeline completo por chat do zero ao código, sem tocar o Kanban manualmente
# ---------------------------------------------------------------------------

async def test_full_pipeline_via_chat_zero_to_code(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput
    from app.services.agents.dev import DevAgent, DevOutput

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    # Reviewer reprovado (sem crítico) -> production, onde o dev roda.
    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=False,
            confidence_score=0.5,
            log_summary="reprovado",
        )

    async def fake_dev(self, plan):  # noqa: ANN001
        return DevOutput(
            code="print('hi')",
            ran_in_sandbox=True,
            sandbox_success=True,
            attempts=1,
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)
    monkeypatch.setattr(DevAgent, "run", fake_dev)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "seguir com a pesquisa")
    await _turn(client, cid, "fazer o plano")
    await _turn(client, cid, "revisar")
    body = await _turn(client, cid, "gerar o codigo")

    card_id = body["card_id"]
    assert card_id is not None

    # O card chegou a 'done' sem PATCH manual de coluna.
    card = await client.get("/api/v1/cards/" + card_id)
    assert card.json()["data"]["column"] == "done"

    # O artifact 'dev' foi produzido pelo Dev Agent.
    async with session_factory() as s:
        result = await s.execute(
            select(Artifact).where(
                Artifact.card_id == UUID(card_id), Artifact.agent_name == "dev"
            )
        )
        assert result.scalars().first() is not None

    # Histórico de mensagens registrou user + tool + conductor.
    msgs = await client.get(f"/api/v1/conversations/{cid}/messages")
    roles = [m["role"] for m in msgs.json()["data"]["messages"]]
    assert "user" in roles
    assert "conductor" in roles
    assert "tool" in roles
    assert all(r in MSG_ROLES for r in roles)


# ---------------------------------------------------------------------------
# 7) Conductor publica card.updated no EventBus (tempo real via WebSocket)
# ---------------------------------------------------------------------------

async def test_conductor_publishes_card_updated_event(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.ideation import IdeationAgent, IdeationOutput
    from app.services.event_bus import Event

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    # Captura os eventos publicados sem afetar o bus global (spy no publish).
    from app.services.event_bus import event_bus

    published: list = []

    real_publish = event_bus.publish

    def _spy_publish(event: Event) -> None:
        published.append(event)
        # Não propaga para os subscribers reais (mantém o teste isolado).
        return None

    monkeypatch.setattr(event_bus, "publish", _spy_publish)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    await _turn(client, cid, "quero criar um app de caronas pra faculdade")

    updated = [e for e in published if e.type == "card.updated"]
    assert updated, "Conductor deve publicar card.updated no EventBus"
    payload = updated[-1].payload
    assert payload["column"] == "researching"
    assert payload["project_id"] == pid
    assert payload["card_id"]
