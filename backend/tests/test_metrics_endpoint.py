"""Testes TDD do endpoint GET /api/v1/metrics/insights (Fase C1)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project

pytestmark = pytest.mark.asyncio


def _utc(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


async def _seed(session_factory: async_sessionmaker) -> None:
    async with session_factory() as s:
        proj = Project(name="Alpha")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, title="A", column="done", auto_approved=True)
        s.add(card)
        await s.commit()
        await s.refresh(card)
        s.add(
            Execution(
                card_id=card.id,
                agent_name="dev",
                status="success",
                cost_usd=2.0,
                duration_ms=1500,
                started_at=_utc(0),
            )
        )
        await s.commit()


async def test_metrics_endpoint_returns_envelope(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await _seed(session_factory)
    resp = await client.get("/api/v1/metrics/insights?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "request_id" in body["meta"]
    data = body["data"]
    assert data["days"] == 30
    assert round(data["total_cost_usd"], 4) == 2.0
    assert "cost_by_project" in data
    assert "cost_by_agent" in data
    assert "auto_approve_rate" in data


async def test_metrics_endpoint_default_days(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await _seed(session_factory)
    resp = await client.get("/api/v1/metrics/insights")
    assert resp.status_code == 200
    assert resp.json()["data"]["days"] == 30


async def test_metrics_endpoint_rejects_invalid_days(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    resp = await client.get("/api/v1/metrics/insights?days=0")
    assert resp.status_code == 422


async def test_metrics_endpoint_requires_auth(
    anon_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    resp = await anon_client.get("/api/v1/metrics/insights")
    assert resp.status_code == 401
