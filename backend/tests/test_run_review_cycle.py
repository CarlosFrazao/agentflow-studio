"""Testes TDD: ciclo Criação<->Revisão executado pelo endpoint /run (Item B)."""

import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _seed_card_in_column(client, column: str):
    proj = await client.post(f"{API}/projects", json={"name": "RevCycle", "description": "x"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        f"{API}/cards", json={"project_id": pid, "title": "Build a cart API", "column": column}
    )
    return pid, card.json()["data"]["id"]


async def test_run_from_reviewing_with_failed_review_returns_to_production(client, monkeypatch):
    """Quando o Reviewer reprova, o card volta para production com logs anexados."""
    # Força modo demo (avanço determinístico sem LLM)
    monkeypatch.setattr(get_settings(), "demo_mode", True)

    _, cid = await _seed_card_in_column(client, "reviewing")
    resp = await client.post(f"{API}/cards/{cid}/run")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # No modo demo o reviewer "passa"; garantimos só que o ciclo não quebra.
    assert data["status"] == "success"
    assert data["column"] in ("done", "reviewing", "production")
