"""Motor de insights de uso/custo do Dashboard (Fase C1 / F-013).

Deriva métricas de uso e custo diretamente do schema do AgentFlow
(``Execution``, ``Card``, ``Project``, ``BudgetLimit``), sem depender de
serviços externos. Alimenta o endpoint ``GET /api/v1/metrics/insights``.

Métricas expostas (janela de ``days`` dias, baseada em ``Execution.started_at``):
- ``total_cost_usd``        — soma de custo das execuções na janela.
- ``cost_by_project``       — custo + contagem por projeto (join Card→Project).
- ``cost_by_agent``         — custo + contagem por agente (fase).
- ``avg_time_per_phase``    — média de ``duration_ms`` por agente.
- ``auto_approve_rate``     — fração de cards ``auto_approved`` (ADR-007).
- ``reversal_rate``         — fração de cards com ``meta.review_logs`` (ciclo
                              Criação↔Revisão reprovado — Item B do PRD).
- ``spend_vs_limit``        — gasto vs limite mensal (respeita BudgetLimit, F-011).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.budget import BudgetLimit
from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project

logger = get_logger("metrics_insights")

DEFAULT_WINDOW_DAYS = 30

# Join implícito Execution->Card->Project para restringir tudo ao dono.
_CARD_PROJECT_JOIN = (
    Execution.__table__.join(Card, Execution.card_id == Card.id)
    .join(Project, Card.project_id == Project.id)
)


@dataclass
class MetricsReport:
    """Relatório agregado de métricas de uso/custo."""

    days: int
    total_cost_usd: float
    cost_by_project: dict[str, dict[str, Any]] = field(default_factory=dict)
    cost_by_agent: dict[str, dict[str, Any]] = field(default_factory=dict)
    avg_time_per_phase: dict[str, float] = field(default_factory=dict)
    auto_approve_rate: float = 0.0
    reversal_rate: float = 0.0
    spend_vs_limit: dict[str, float] = field(
        default_factory=lambda: {"spent_usd": 0.0, "limit_usd": 0.0, "ratio": 0.0}
    )


class InsightsEngine:
    """Gera o ``MetricsReport`` a partir do banco de dados assíncrono."""

    def __init__(self, db_session: AsyncSession, user_id: UUID | None = None) -> None:
        self._session = db_session
        # Quando None, mantém o comportamento global legado (usado por testes
        # que não autenticam). Com um user_id, todo o relatório é restrito ao
        # tenant daquele usuário (Project.user_id).
        self._user_id = user_id

    async def generate(self, days: int = DEFAULT_WINDOW_DAYS) -> MetricsReport:
        """Agrega métricas das execuções dos últimos ``days`` dias.

        Levanta ``ValueError`` se ``days`` não for positivo.
        """
        if days <= 0:
            raise ValueError("days deve ser um inteiro positivo")

        since = datetime.now(tz=timezone.utc) - timedelta(days=days)

        total_cost = await self._total_cost(since)
        cost_by_project = await self._cost_by_project(since)
        cost_by_agent = await self._cost_by_agent(since)
        avg_time = await self._avg_time_per_phase(since)
        auto_rate, reversal_rate = await self._card_rates(since)
        spend_vs_limit = await self._spend_vs_limit()

        report = MetricsReport(
            days=days,
            total_cost_usd=round(total_cost, 4),
            cost_by_project=cost_by_project,
            cost_by_agent=cost_by_agent,
            avg_time_per_phase=avg_time,
            auto_approve_rate=auto_rate,
            reversal_rate=reversal_rate,
            spend_vs_limit=spend_vs_limit,
        )
        logger.info(
            "insights_generated",
            days=days,
            total_cost_usd=report.total_cost_usd,
            projects=len(cost_by_project),
            agents=len(cost_by_agent),
        )
        return report

    def _user_filter(self, *cols):
        """Aplica o filtro de tenant (Project.user_id) quando há user_id."""
        if self._user_id is None:
            return None
        return Project.user_id == self._user_id

    async def _total_cost(self, since: datetime) -> float:
        stmt = select(func.coalesce(func.sum(Execution.cost_usd), 0.0)).where(
            Execution.started_at >= since
        )
        if self._user_id is not None:
            stmt = (
                stmt.select_from(_CARD_PROJECT_JOIN)
                .where(Project.user_id == self._user_id)
            )
        value = await self._session.scalar(stmt)
        return float(value or 0.0)

    async def _cost_by_project(self, since: datetime) -> dict[str, dict[str, Any]]:
        stmt = (
            select(
                Project.id,
                Project.name,
                func.coalesce(func.sum(Execution.cost_usd), 0.0).label("cost"),
                func.count(Execution.id).label("exec_count"),
            )
            .select_from(Execution)
            .join(Card, Execution.card_id == Card.id)
            .join(Project, Card.project_id == Project.id)
            .where(Execution.started_at >= since)
        )
        if self._user_id is not None:
            stmt = stmt.where(Project.user_id == self._user_id)
        rows = (await self._session.execute(stmt.group_by(Project.id, Project.name).order_by(func.sum(Execution.cost_usd).desc()))).all()
        return {
            str(pid): {
                "name": name,
                "cost_usd": round(float(cost), 4),
                "exec_count": int(cnt),
            }
            for pid, name, cost, cnt in rows
        }

    async def _cost_by_agent(self, since: datetime) -> dict[str, dict[str, Any]]:
        stmt = (
            select(
                Execution.agent_name,
                func.coalesce(func.sum(Execution.cost_usd), 0.0).label("cost"),
                func.count(Execution.id).label("exec_count"),
            )
            .where(Execution.started_at >= since)
        )
        if self._user_id is not None:
            stmt = (
                stmt.select_from(_CARD_PROJECT_JOIN)
                .where(Project.user_id == self._user_id)
            )
        rows = (await self._session.execute(stmt.group_by(Execution.agent_name).order_by(func.sum(Execution.cost_usd).desc()))).all()
        return {
            name: {"cost_usd": round(float(cost), 4), "exec_count": int(cnt)}
            for name, cost, cnt in rows
        }

    async def _avg_time_per_phase(self, since: datetime) -> dict[str, float]:
        stmt = (
            select(
                Execution.agent_name,
                func.avg(Execution.duration_ms).label("avg_ms"),
            )
            .where(Execution.started_at >= since)
        )
        if self._user_id is not None:
            stmt = (
                stmt.select_from(_CARD_PROJECT_JOIN)
                .where(Project.user_id == self._user_id)
            )
        rows = (await self._session.execute(stmt.group_by(Execution.agent_name))).all()
        return {name: round(float(avg_ms or 0.0), 4) for name, avg_ms in rows}

    async def _card_rates(self, since: datetime) -> tuple[float, float]:
        """Taxa de auto-approve e taxa de reversão sobre os cards na janela.

        Ambas as contagens são filtradas por ``updated_at >= since`` (ADR A5:
        a métrica reflete apenas a janela de ``days``, sem materializar todos
        os ``meta`` do banco — evita o scan O(N) anterior). Quando há user_id,
        restringe aos projetos do usuário.

        - auto-approve: cards com ``auto_approved = True`` (persistido pelo
          fluxo /run via ``should_auto_approve``, ADR-007).
        - reversão: cards cujo ``meta`` contém ``review_logs`` (o Reviewer
          reprovou e devolveu o card para 'production' — ciclo Criação↔Revisão).
        """
        from sqlalchemy.orm import selectinload

        card_stmt = select(Card).where(Card.updated_at >= since)
        if self._user_id is not None:
            card_stmt = card_stmt.join(Project, Card.project_id == Project.id).where(
                Project.user_id == self._user_id
            )
        total = (
            await self._session.scalar(
                select(func.count()).select_from(card_stmt.subquery())
            )
            or 0
        )
        if total == 0:
            return 0.0, 0.0

        auto_stmt = select(func.count()).select_from(Card).where(
            Card.auto_approved.is_(True), Card.updated_at >= since
        )
        if self._user_id is not None:
            auto_stmt = auto_stmt.join(Project, Card.project_id == Project.id).where(
                Project.user_id == self._user_id
            )
        auto_count = (await self._session.scalar(auto_stmt)) or 0

        # meta é JSON; contar via presença da chave review_logs é mais portável
        # em Python do que via operadores JSON específicos de dialeto. O filtro
        # por janela já roda no SQL (updated_at >= since), então só os cards
        # relevantes têm o meta materializado.
        meta_stmt = select(Card.meta).where(Card.updated_at >= since)
        if self._user_id is not None:
            meta_stmt = meta_stmt.join(Project, Card.project_id == Project.id).where(
                Project.user_id == self._user_id
            )
        cards_meta = (await self._session.scalars(meta_stmt)).all()
        reversal_count = sum(
            1
            for meta in cards_meta
            if isinstance(meta, dict) and meta.get("review_logs")
        )

        return round(auto_count / total, 6), round(reversal_count / total, 6)

    async def _spend_vs_limit(self) -> dict[str, float]:
        stmt = select(
            func.coalesce(func.sum(BudgetLimit.current_month_spend_usd), 0.0),
            func.coalesce(func.sum(BudgetLimit.monthly_limit_usd), 0.0),
        )
        if self._user_id is not None:
            stmt = stmt.where(BudgetLimit.user_id == self._user_id)
        spend_row = await self._session.execute(stmt)
        spent, limit = spend_row.one()
        spent = float(spent or 0.0)
        limit = float(limit or 0.0)
        ratio = (spent / limit) if limit else 0.0
        return {
            "spent_usd": round(spent, 4),
            "limit_usd": round(limit, 4),
            "ratio": round(ratio, 4),
        }

    def format_dashboard(self, report: MetricsReport) -> dict[str, Any]:
        """Serializa o ``MetricsReport`` para o payload JSON do dashboard."""
        return {
            "days": report.days,
            "total_cost_usd": report.total_cost_usd,
            "cost_by_project": report.cost_by_project,
            "cost_by_agent": report.cost_by_agent,
            "avg_time_per_phase": report.avg_time_per_phase,
            "auto_approve_rate": report.auto_approve_rate,
            "reversal_rate": report.reversal_rate,
            "spend_vs_limit": report.spend_vs_limit,
        }
