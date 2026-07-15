"""Testes adicionais do endpoint /run (Item 5 — cobertura de run.py).

Cobre: modo demo, falha de agente (exception path) e ciclo de revisão
(revisor reprovado devolve para production).
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _seed_card_in_column(client: AsyncClient, column: str) -> tuple[str, str]:
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Ideia", "column": column}
    )
    return pid, card.json()["data"]["id"]


async def test_run_demo_mode_advances_column(client, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_mode", True)
    _, cid = await _seed_card_in_column(client, "backlog")
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["demo"] is True
    assert body["status"] == "success"


async def test_run_agent_failure_returns_failed(client, monkeypatch) -> None:
    from app.services.agents.ideation import IdeationAgent

    async def boom(self, raw_idea: str):
        raise RuntimeError("agent quebrou")

    monkeypatch.setattr(IdeationAgent, "run", boom)
    _, cid = await _seed_card_in_column(client, "backlog")
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "failed"


async def test_run_reviewer_fail_returns_to_production(client, monkeypatch) -> None:
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput

    async def fake_review(self, **kwargs) -> ReviewOutput:
        return ReviewOutput(
            alerts=[],
            critical_count=2,
            passed=False,
            confidence_score=0.3,
            log_summary="erro crítico",
        )

    monkeypatch.setattr(ReviewerAgent, "run", fake_review)
    _, cid = await _seed_card_in_column(client, "reviewing")
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    card = await client.get(f"/api/v1/cards/{cid}")
    data = card.json()["data"]
    assert data["column"] == "production"
    assert "review_logs" in (data["meta"] or {})


async def test_run_reviewer_pass_advances_to_done(client, monkeypatch) -> None:
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput

    async def fake_review(self, **kwargs) -> ReviewOutput:
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=True,
            confidence_score=0.95,
            log_summary=None,
        )

    monkeypatch.setattr(ReviewerAgent, "run", fake_review)
    _, cid = await _seed_card_in_column(client, "reviewing")
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    card = await client.get(f"/api/v1/cards/{cid}")
    assert card.json()["data"]["column"] == "done"


async def test_run_dev_uses_configured_sandbox_backend(client, monkeypatch) -> None:
    from app.services.agents.dev import DevAgent, DevOutput
    from app.sandbox.base import SandboxResult

    class FakeLLM:
        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            return "print('ok')"

    class OkSandbox:
        name = "fake"

        async def validate(self, code: str) -> SandboxResult:
            return SandboxResult(success=True, stderr="", backend="fake")

    async def fake_dev_run(self, plan: str) -> DevOutput:
        return DevOutput(code="print('ok')", ran_in_sandbox=True, sandbox_success=True, attempts=1)

    monkeypatch.setattr(DevAgent, "run", fake_dev_run)
    import app.sandbox.base as sandbox_base

    monkeypatch.setattr(sandbox_base, "get_sandbox_backend", lambda: OkSandbox())

    _, cid = await _seed_card_in_column(client, "production")
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "success"
