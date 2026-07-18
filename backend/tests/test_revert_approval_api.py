"""Testes TDD da rota POST /cards/{id}/revert-approval (FEAT-009).

Cobre os 3 cenarios do PRD §4.9.2 / task.md Bloco 9:
- revert dentro da janela (200 + publica card.updated)
- fora da janela (400 APPROVAL_WINDOW_EXPIRED)
- card ja manual (idempotente: 200 reverted=False, sem mover coluna)

IMPORTANTE (FEAT-006): o POST /cards IGNORA os campos de auto-approve
(approval_by/auto_approved/revert_deadline) — um cliente nao pode forjar um
card auto-aprovado. Por isso o card auto-aprovado destes testes e semeado
DIRETO no banco (via modelo Card), e nao via POST /cards.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.card import Card

pytestmark = pytest.mark.asyncio


async def _seed_auto_approved_card(
    client: AsyncClient,
    session_factory,
    *,
    deadline: datetime | None,
    column: str = "done",
) -> str:
    """Cria projeto (via API) + card auto-aprovado (via DB direto).

    O card auto-aprovado e semeado pelo modelo para contornar o bloqueio de
    FEAT-006 no POST /cards (que agora ignora approval_by/auto_approved/
    revert_deadline vindos do cliente).
    """
    proj = await client.post("/api/v1/projects", json={"name": "Revert"})
    pid = proj.json()["data"]["id"]
    async with session_factory() as s:
        card = Card(
            project_id=uuid4() if pid is None else UUID(pid),
            title="Auto aprovado",
            column=column,
            confidence_score=0.9,
            approval_by="auto",
            auto_approved=True,
            revert_deadline=deadline,
        )
        s.add(card)
        await s.commit()
        await s.refresh(card)
        return str(card.id)


async def test_revert_within_window(client: AsyncClient, session_factory) -> None:
    future = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
    cid = await _seed_auto_approved_card(client, session_factory, deadline=future, column="done")

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


async def test_revert_outside_window_400(client: AsyncClient, session_factory) -> None:
    past = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
    cid = await _seed_auto_approved_card(client, session_factory, deadline=past, column="done")

    resp = await client.post(f"/api/v1/cards/{cid}/revert-approval")
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "APPROVAL_WINDOW_EXPIRED"

    # O card NAO mudou de coluna (reversao nao aplicada).
    refreshed = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    assert refreshed["column"] == "done"
    assert refreshed["auto_approved"] is True


async def test_revert_already_manual_idempotent(client: AsyncClient) -> None:
    """Card manual (nao auto-aprovado) e idempotente: 200 reverted=False,
    sem mover coluna."""
    proj = await client.post("/api/v1/projects", json={"name": "Manual"})
    pid = proj.json()["data"]["id"]
    created = await client.post(
        "/api/v1/cards",
        json={
            "project_id": pid,
            "title": "Manual",
            "column": "done",
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
