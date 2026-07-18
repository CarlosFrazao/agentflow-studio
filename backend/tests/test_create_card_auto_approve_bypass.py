"""FEAT-006: a client must NOT be able to forge an auto-approved card via POST /cards.

The auto-approve fields (approval_by / auto_approved / revert_deadline) are
server-controlled only — set via POST /run (ADR-007) or /revert-approval.
A freshly created card must always start as not auto-approved, otherwise the
Human-in-the-Loop gate could be bypassed by a malicious client.
"""

import pytest
from httpx import AsyncClient

from app.schemas.card import CardCreate


def test_card_create_schema_has_no_auto_approve_fields() -> None:
    """Root-cause closure: the schema itself must not accept the fields."""
    assert "approval_by" not in CardCreate.model_fields
    assert "auto_approved" not in CardCreate.model_fields
    assert "revert_deadline" not in CardCreate.model_fields


@pytest.mark.asyncio
async def test_create_card_ignores_auto_approve(client: AsyncClient) -> None:
    """A POST /cards carrying auto_approved=true, approval_by='auto' and a
    revert_deadline must NOT create an auto-approved card."""
    proj = await client.post("/api/v1/projects", json={"name": "Bypass"})
    pid = proj.json()["data"]["id"]

    from datetime import datetime, timedelta, timezone

    future = (datetime.now(tz=timezone.utc) + timedelta(minutes=10)).isoformat()
    resp = await client.post(
        "/api/v1/cards",
        json={
            "project_id": pid,
            "title": "Tentativa de bypass",
            "column": "backlog",
            "approval_by": "auto",
            "auto_approved": True,
            "revert_deadline": future,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["auto_approved"] is False
    assert data["approval_by"] == "none"
    assert data["revert_deadline"] is None


@pytest.mark.asyncio
async def test_create_card_basic(client: AsyncClient) -> None:
    """Regression: a normal card create still works and starts manual."""
    proj = await client.post("/api/v1/projects", json={"name": "Basico"})
    pid = proj.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/cards",
        json={"project_id": pid, "title": "Card normal", "column": "backlog"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["title"] == "Card normal"
    assert data["column"] == "backlog"
    assert data["auto_approved"] is False
    assert data["approval_by"] == "none"
    assert data["revert_deadline"] is None
