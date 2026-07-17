"""Testes TDD da rota POST /cards/{id}/revert-approval (FEAT-009).

Cobre os 3 cenários do PRD §4.9.2 / task.md Bloco 9:
- revert dentro da janela (200 + publica card.updated)
- fora da janela (400 APPROVAL_WINDOW_EXPIRED)
- card já manual (idempotente: 200 reverted=False, sem mover coluna)
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.asyncio


async def _create_auto_approved_card(
    client: AsyncClient,
    *,
    deadline: datetime | None,
    column: str = "done",
) -> str:
    """Cria projeto + card auto-aprovado com revert_deadline e coluna dadas."""
    proj = await client.post("/api/v1/projects", json={"name": "Revert"})
    pid = proj.json()["data"]["id"]
    created = await client.post(
        "/api/v1/cards",
        json={
            "project_id": pid,
            "title": "Auto aprovado",
            "column": column,
            "confidence_score": 0.9,
            "approval_by": "auto",
            "auto_approved": True,
            "revert_deadline": deadline.isoformat() if deadline else None,
        },
    )
    return created.json()["data"]["id"]


async def test_revert_within_window(client: AsyncClient) -> None:
    future = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
    cid = await _create_auto_approved_card(client, deadline=future, column="done")

    resp = await client.post(f"/api/v1/cards/{cid}/revert-approval")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["card_id"] == cid
    assert body["data"]["reverted"] is True

    # O card voltou para a coluna anterior ('done' -> 'production').
    refreshed = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    assert refreshed["column"] == "production"
    assert refreshed["auto_approved"] is False
    assert refreshed["approval_by"] == "none"
    assert refreshed["revert_deadline"] is None


async def test_revert_outside_window_400(client: AsyncClient) -> None:
    past = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
    cid = await _create_auto_approved_card(client, deadline=past, column="done")

    resp = await client.post(f"/api/v1/cards/{cid}/revert-approval")
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "APPROVAL_WINDOW_EXPIRED"

    # O card NÃO mudou de coluna (reversão não aplicada).
    refreshed = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    assert refreshed["column"] == "done"
    assert refreshed["auto_approved"] is True


async def test_revert_already_manual_idempotent(client: AsyncClient) -> None:
    """Card manual (não auto-aprovado) é idempotente: 200 reverted=False,
    sem mover coluna."""
    proj = await client.post("/api/v1/projects", json={"name": "Manual"})
    pid = proj.json()["data"]["id"]
    created = await client.post(
        "/api/v1/cards",
        json={
            "project_id": pid,
            "title": "Manual",
            "column": "done",
            "approval_by": "human",
            "auto_approved": False,
        },
    )
    cid = created.json()["data"]["id"]

    resp = await client.post(f"/api/v1/cards/{cid}/revert-approval")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["reverted"] is False

    refreshed = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    assert refreshed["column"] == "done"
    assert refreshed["auto_approved"] is False
