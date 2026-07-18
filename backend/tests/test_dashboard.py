"""Testes TDD do Dashboard de Métricas (F-013 simplificado)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _seed(client: AsyncClient) -> str:
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Ideia", "column": "done"}
    )
    return card.json()["data"]["id"]


async def test_dashboard_returns_metrics_shape(client: AsyncClient) -> None:
    await _seed(client)
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    # métricas essenciais do PRD F-013
    assert "projects_created" in data
    assert "cards_done" in data
    assert "total_cost_usd" in data
    assert "spend_vs_limit" in data


async def test_dashboard_lists_recent_executions(client: AsyncClient) -> None:
    await _seed(client)
    resp = await client.get("/api/v1/dashboard")
    assert "recent_executions" in resp.json()["data"]
    assert isinstance(resp.json()["data"]["recent_executions"], list)


async def test_dashboard_spend_vs_limit_ratio(
    client: AsyncClient, session_factory
) -> None:
    # FEAT-002: current_month_spend_usd nao e mais settable via API (anti-fraude);
    # o gasto e semeado direto no banco. FEAT-008: o dashboard filtra por
    # current_user, entao o budget deve pertencer ao usuario autenticado pelo
    # fixture `client` (nao a um user arbitrario).
    from app.api.v1.deps import get_current_user
    from app.models.budget import BudgetLimit
    from sqlalchemy import select

    override = client._transport.app.dependency_overrides.get(get_current_user)
    auth_user = await override()
    uid = auth_user.id
    async with session_factory() as s:
        budget = await s.scalar(
            select(BudgetLimit).where(BudgetLimit.user_id == uid)
        )
        if budget is None:
            budget = BudgetLimit(user_id=uid)
            s.add(budget)
        budget.monthly_limit_usd = 10.0
        budget.per_project_limit_usd = 3.0
        budget.current_month_spend_usd = 5.0
        await s.commit()
    resp = await client.get("/api/v1/dashboard")
    data = resp.json()["data"]
    assert data["spend_vs_limit"]["limit_usd"] == 10.0
    assert data["spend_vs_limit"]["spent_usd"] == 5.0
    assert data["spend_vs_limit"]["ratio"] == 0.5
