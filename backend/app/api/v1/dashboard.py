"""Dashboard de Métricas (F-013, incluindo expansão v1.2).

MVP: cards essenciais (projetos, cards done, custo total, gasto vs limite) +
tabela de execuções recentes.

v1.2: agregações para visibilidade de custo — série temporal (custo por dia,
últimos 30 dias), custo por agente, contagem por status, e filtro opcional
por projeto (drill-down). Sem colunas novas: reusa Execution.started_at,
cost_usd, agent_name, status e Card.project_id.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_request_id
from app.core.database import get_session
from app.core.responses import success_envelope
from app.models.budget import BudgetLimit
from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Janela da série temporal de custo (dias).
COST_SERIES_DAYS = 30


def _execution_base_query(user: User, project_id: UUID | None):
    """Query base de Execution restrita ao usuário.

    Sempre filtra pelos cards dos projetos do usuário; se ``project_id`` for
    informado, restringe ainda mais àquele projeto (drill-down). Isso evita
    que o dashboard exponha execuções/custos de outros usuários (tenant scope).
    """
    q = (
        select(Execution)
        .join(Card, Execution.card_id == Card.id)
        .join(Project, Card.project_id == Project.id)
        .where(Project.user_id == user.id)
    )
    if project_id is not None:
        q = q.where(Card.project_id == project_id)
    return q


@router.get("", response_model=None)
async def get_dashboard(
    request: Request,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    project_id: UUID | None = Query(default=None, description="Filtrar por projeto (drill-down)"),
) -> dict:
    # Escopo de tenant: só os recursos do usuário autenticado.
    projects_created = (
        await session.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.user_id == user.id)
        )
        or 0
    )
    cards_done = (
        await session.scalar(
            select(func.count())
            .select_from(Card)
            .join(Project, Card.project_id == Project.id)
            .where(Project.user_id == user.id, Card.column == "done")
        )
        or 0
    )

    # gasto vs limite — SOMENTE dos budgets do usuário (nunca global)
    spend_row = await session.execute(
        select(
            func.coalesce(func.sum(BudgetLimit.current_month_spend_usd), 0.0),
            func.coalesce(func.sum(BudgetLimit.monthly_limit_usd), 0.0),
        ).where(BudgetLimit.user_id == user.id)
    )
    spent, limit = spend_row.one()
    ratio = (spent / limit) if limit else 0.0

    base_exec = _execution_base_query(user, project_id)
    # Fonte para agregações: subquery com join/filtro de tenant, preservando
    # as colunas via `.c` para evitar ambiguidade.
    subq = base_exec.subquery()
    src = subq
    c_started = subq.c.started_at
    c_cost = subq.c.cost_usd
    c_agent = subq.c.agent_name
    c_status = subq.c.status
    c_id = subq.c.id

    # custo total (respeita filtro de tenant + projeto quando presente)
    total_cost = (
        await session.scalar(select(func.coalesce(func.sum(c_cost), 0.0)).select_from(src))
        or 0.0
    )

    # execuções recentes (últimas 20, respeitando filtro de tenant/projeto)
    rows = (
        await session.scalars(
            base_exec.order_by(Execution.started_at.desc().nullslast()).limit(20)
        )
    ).all()
    recent = [
        {
            "id": str(e.id),
            "card_id": str(e.card_id),
            "agent_name": e.agent_name,
            "status": e.status,
            "duration_ms": e.duration_ms,
            "cost_usd": e.cost_usd,
        }
        for e in rows
    ]

    # série temporal de custo (últimos COST_SERIES_DAYS dias)
    cost_series_rows = (
        await session.execute(
            select(
                func.date(c_started).label("day"),
                func.coalesce(func.sum(c_cost), 0.0).label("cost"),
            )
            .select_from(src)
            .where(c_started.isnot(None))
            .group_by(func.date(c_started))
            .order_by(func.date(c_started).desc())
            .limit(COST_SERIES_DAYS)
        )
    ).all()
    cost_by_day = [
        {"date": str(day), "cost_usd": round(float(cost), 4)}
        for day, cost in cost_series_rows
    ]

    # custo por agente (top agregado)
    agent_rows = (
        await session.execute(
            select(
                c_agent,
                func.coalesce(func.sum(c_cost), 0.0).label("cost"),
                func.count(c_id).label("exec_count"),
            )
            .select_from(src)
            .group_by(c_agent)
            .order_by(func.sum(c_cost).desc())
        )
    ).all()
    cost_by_agent = [
        {"agent_name": name, "cost_usd": round(float(cost), 4), "exec_count": int(cnt)}
        for name, cost, cnt in agent_rows
    ]

    # contagem por status
    status_rows = (
        await session.execute(
            select(c_status, func.count(c_id)).select_from(src).group_by(c_status)
        )
    ).all()
    executions_by_status = {status: int(cnt) for status, cnt in status_rows}

    return success_envelope(
        data={
            "projects_created": projects_created,
            "cards_done": cards_done,
            "total_cost_usd": round(float(total_cost), 4),
            "spend_vs_limit": {
                "spent_usd": round(float(spent), 4),
                "limit_usd": round(float(limit), 4),
                "ratio": round(float(ratio), 4),
            },
            "recent_executions": recent,
            "cost_by_day": cost_by_day,
            "cost_by_agent": cost_by_agent,
            "executions_by_status": executions_by_status,
        },
        request_id=request_id,
    )
