"""Testes TDD do Dashboard v1.2 (F-013): agregações de custo e filtro.

Cobertura:
- série temporal de custo por dia (últimos 30 dias)
- custo agregado por agente
- contagem por status de execução
- filtro opcional por projeto (drill-down isola execuções de outro projeto)
- envelope retrocompatível (campos do MVP preservados)
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project

pytestmark = pytest.mark.asyncio


def _utc(days_ago: int, hour: int = 12) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=24 - hour)


async def _make_project(session_factory: async_sessionmaker, name: str) -> str:
    async with session_factory() as s:
        p = Project(name=name)
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return str(p.id)


async def _make_card(session_factory: async_sessionmaker, project_id: str) -> str:
    async with session_factory() as s:
        c = Card(project_id=UUID(project_id), title="c", column="done")
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return str(c.id)


async def _add_exec(
    session_factory: async_sessionmaker,
    card_id: str,
    agent: str,
    cost: float,
    status: str,
    days_ago: int,
) -> None:
    async with session_factory() as s:
        e = Execution(
            card_id=UUID(card_id),
            agent_name=agent,
            status=status,
            cost_usd=cost,
            duration_ms=100,
            started_at=_utc(days_ago),
            finished_at=_utc(days_ago),
        )
        s.add(e)
        await s.commit()


async def _seed_two_projects(
    client: AsyncClient, session_factory: async_sessionmaker
) -> tuple[str, str]:
    """Cria 2 projetos, cada um com 1 card e execuções distintas."""
    pid_a = await _make_project(session_factory, "A")
    pid_b = await _make_project(session_factory, "B")
    cid_a = await _make_card(session_factory, pid_a)
    cid_b = await _make_card(session_factory, pid_b)

    # Projeto A: ideation (ontem) + dev (hoje)
    await _add_exec(session_factory, cid_a, "ideation", 1.0, "success", days_ago=1)
    await _add_exec(session_factory, cid_a, "dev", 2.0, "success", days_ago=0)
    # Projeto B: reviewer (hoje) com falha
    await _add_exec(session_factory, cid_b, "reviewer", 5.0, "failed", days_ago=0)
    return pid_a, pid_b


async def test_dashboard_v12_shape_global(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await _seed_two_projects(client, session_factory)
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()["data"]

    # retrocompatibilidade: campos do MVP preservados
    for key in (
        "projects_created",
        "cards_done",
        "total_cost_usd",
        "spend_vs_limit",
        "recent_executions",
    ):
        assert key in data

    # novos campos v1.2
    assert "cost_by_day" in data
    assert "cost_by_agent" in data
    assert "executions_by_status" in data
    assert isinstance(data["cost_by_day"], list)
    assert isinstance(data["cost_by_agent"], list)
    assert isinstance(data["executions_by_status"], dict)


async def test_dashboard_cost_by_agent_aggregates(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await _seed_two_projects(client, session_factory)
    resp = await client.get("/api/v1/dashboard")
    data = resp.json()["data"]

    by_agent = {a["agent_name"]: a for a in data["cost_by_agent"]}
    # reviewer (proj B) custou 5.0; dev (proj A) 2.0; ideation (proj A) 1.0
    assert by_agent["reviewer"]["cost_usd"] == 5.0
    assert by_agent["dev"]["cost_usd"] == 2.0
    assert by_agent["ideation"]["cost_usd"] == 1.0
    # ordenado por custo desc -> reviewer primeiro
    assert data["cost_by_agent"][0]["agent_name"] == "reviewer"
    # exec_count presente
    assert by_agent["ideation"]["exec_count"] == 1


async def test_dashboard_executions_by_status(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await _seed_two_projects(client, session_factory)
    resp = await client.get("/api/v1/dashboard")
    status = resp.json()["data"]["executions_by_status"]
    assert status.get("success") == 2
    assert status.get("failed") == 1


async def test_dashboard_cost_by_day_series(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await _seed_two_projects(client, session_factory)
    resp = await client.get("/api/v1/dashboard")
    series = resp.json()["data"]["cost_by_day"]
    # 2 dias distintos (ontem + hoje) com execuções
    days = {row["date"] for row in series}
    assert len(days) == 2
    total = sum(row["cost_usd"] for row in series)
    assert round(total, 4) == 8.0  # 1+2+5


async def test_dashboard_filter_by_project_isolates(
    client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    pid_a, pid_b = await _seed_two_projects(client, session_factory)

    # filtra pelo projeto A: só ideation(1.0) + dev(2.0) = 3.0
    resp = await client.get("/api/v1/dashboard", params={"project_id": pid_a})
    data = resp.json()["data"]
    assert round(data["total_cost_usd"], 4) == 3.0
    by_agent = {a["agent_name"]: a for a in data["cost_by_agent"]}
    assert set(by_agent.keys()) == {"ideation", "dev"}
    assert "reviewer" not in by_agent

    # filtra pelo projeto B: só reviewer(5.0)
    resp_b = await client.get("/api/v1/dashboard", params={"project_id": pid_b})
    data_b = resp_b.json()["data"]
    assert round(data_b["total_cost_usd"], 4) == 5.0
    by_agent_b = {a["agent_name"]: a for a in data_b["cost_by_agent"]}
    assert set(by_agent_b.keys()) == {"reviewer"}
