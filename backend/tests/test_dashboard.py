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
    # O router /users (CRUD de User) foi removido no FEAT-C001 (mitiga IDOR
    # em massa). O user e' criado via /auth/register.
    # FEAT-002: current_month_spend_usd nao e mais settable via API (anti-fraude);
    # o gasto e semeado direto no banco, como as Executions fariam. O dashboard
    # soma os budgets globalmente, entao criamos um unico budget controlado.
    from uuid import UUID

    from app.models.budget import BudgetLimit
    from sqlalchemy import select

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "d@ex.com", "display_name": "D", "password": "x12345678"},
    )
    uid = reg.json()["data"]["user"]["id"]
    async with session_factory() as s:
        budget = await s.scalar(
            select(BudgetLimit).where(BudgetLimit.user_id == UUID(uid))
        )
        if budget is None:
            budget = BudgetLimit(user_id=UUID(uid))
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
