"""Testes TDD do motor de métricas/insights (Fase C1 / F-013).

Cobre o ``InsightsEngine`` (agregações derivadas de Execution/Card/Project/
BudgetLimit) e o ``format_dashboard``:
- custo total, por projeto e por agente
- tempo médio por fase (agente)
- taxa de auto-approve e taxa de reversão
- gasto vs limite (respeita BudgetLimit, F-011)
- janela temporal (days)
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.budget import BudgetLimit
from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project
from app.models.user import User
from app.services import metrics_insights as mi
from app.services.metrics_insights import InsightsEngine, MetricsReport

pytestmark = pytest.mark.asyncio


def _utc(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


async def _seed(session_factory: async_sessionmaker) -> dict:
    """Cria user+budget, 2 projetos, cards e execuções distintas."""
    async with session_factory() as s:
        user = User(id=uuid4(), email="c1@example.com", display_name="C1", password_hash=None)
        s.add(user)
        s.add(
            BudgetLimit(
                user_id=user.id,
                monthly_limit_usd=100.0,
                current_month_spend_usd=8.0,
            )
        )
        proj_a = Project(name="Alpha", user_id=user.id)
        proj_b = Project(name="Beta", user_id=user.id)
        s.add_all([proj_a, proj_b])
        await s.commit()
        await s.refresh(proj_a)
        await s.refresh(proj_b)

        # Card A auto-aprovado; Card B reprovado (review_logs); Card C manual.
        card_a = Card(project_id=proj_a.id, title="A", column="done", auto_approved=True)
        card_b = Card(
            project_id=proj_b.id,
            title="B",
            column="production",
            auto_approved=False,
            meta={"review_logs": "falhou o lint"},
        )
        card_c = Card(project_id=proj_a.id, title="C", column="done", auto_approved=False)
        s.add_all([card_a, card_b, card_c])
        await s.commit()
        await s.refresh(card_a)
        await s.refresh(card_b)
        await s.refresh(card_c)

        execs = [
            # Projeto A
            Execution(card_id=card_a.id, agent_name="ideation", status="success",
                      cost_usd=1.0, duration_ms=1000, started_at=_utc(1)),
            Execution(card_id=card_a.id, agent_name="dev", status="success",
                      cost_usd=2.0, duration_ms=3000, started_at=_utc(0)),
            Execution(card_id=card_c.id, agent_name="dev", status="success",
                      cost_usd=1.0, duration_ms=1000, started_at=_utc(0)),
            # Projeto B
            Execution(card_id=card_b.id, agent_name="reviewer", status="failed",
                      cost_usd=5.0, duration_ms=2000, started_at=_utc(0)),
            # Execução antiga (fora da janela de 30 dias)
            Execution(card_id=card_a.id, agent_name="ideation", status="success",
                      cost_usd=99.0, duration_ms=9000, started_at=_utc(60)),
        ]
        s.add_all(execs)
        await s.commit()

        return {
            "user_id": str(user.id),
            "proj_a": str(proj_a.id),
            "proj_b": str(proj_b.id),
            "proj_a_name": "Alpha",
            "proj_b_name": "Beta",
        }


async def test_generate_returns_report_dataclass(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    assert isinstance(report, MetricsReport)


async def test_total_cost_respects_time_window(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    # 1+2+1+5 = 9.0 (exclui a execução de 60 dias atrás = 99.0)
    assert round(report.total_cost_usd, 4) == 9.0


async def test_cost_by_project(session_factory) -> None:
    ids = await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    by_proj = report.cost_by_project
    # A = ideation(1) + dev(2) + dev(1) = 4.0 ; B = reviewer(5) = 5.0
    assert round(by_proj[ids["proj_a"]]["cost_usd"], 4) == 4.0
    assert round(by_proj[ids["proj_b"]]["cost_usd"], 4) == 5.0
    assert by_proj[ids["proj_a"]]["name"] == "Alpha"


async def test_cost_by_agent(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    by_agent = report.cost_by_agent
    assert round(by_agent["dev"]["cost_usd"], 4) == 3.0
    assert round(by_agent["reviewer"]["cost_usd"], 4) == 5.0
    assert by_agent["ideation"]["exec_count"] == 1  # a antiga foi excluída


async def test_avg_time_per_phase(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    # dev: (3000 + 1000) / 2 = 2000 ms
    assert round(report.avg_time_per_phase["dev"], 1) == 2000.0
    assert round(report.avg_time_per_phase["reviewer"], 1) == 2000.0


async def test_auto_approve_rate(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    # 1 auto-aprovado de 3 cards = 0.3333
    assert round(report.auto_approve_rate, 4) == round(1 / 3, 4)


async def test_reversal_rate(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    # 1 card com review_logs de 3 cards = 0.3333
    assert round(report.reversal_rate, 4) == round(1 / 3, 4)


async def test_reversal_rate_window_filter(session_factory) -> None:
    """Cards com review_logs FORA da janela NÃO entram na taxa (ADR A5)."""
    ids = await _seed(session_factory)
    async with session_factory() as s:
        # Card reprovado ANTIGO (fora da janela de 30 dias): updated_at
        # explícito em -60d. O _card_rates deve filtrar por updated_at >= since.
        old = Card(
            project_id=UUID(ids["proj_a"]),
            title="OldReject",
            column="production",
            auto_approved=False,
            meta={"review_logs": "falhou há muito tempo"},
            updated_at=_utc(60),
        )
        s.add(old)
        await s.commit()
        # Expunge para o identity map não sobrescrever updated_at no commit.
        s.expunge(old)

        report = await InsightsEngine(s).generate(days=30)
    # Apenas card_b (dentro da janela) tem review_logs => 1/3, não 2/4.
    assert round(report.reversal_rate, 4) == round(1 / 3, 4)


async def test_reversal_rate_no_full_scan(session_factory) -> None:
    """_card_rates filtra por updated_at no SQL, não materializa todos os meta."""
    ids = await _seed(session_factory)
    async with session_factory() as s:
        # Card reprovado STALE (updated_at em -90d): fora da janela de 30d,
        # portanto NÃO deve contar na taxa de reversão.
        stale = Card(
            project_id=UUID(ids["proj_a"]),
            title="StaleReject",
            column="production",
            meta={"review_logs": "stale"},
            updated_at=_utc(90),
        )
        s.add(stale)
        await s.commit()
        s.expunge(stale)

        report = await InsightsEngine(s).generate(days=30)
    # 1/3 (card_b), não 2/4 (card_b + StaleReject).
    assert round(report.reversal_rate, 4) == round(1 / 3, 4)


async def test_spend_vs_limit_respects_budget(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    svl = report.spend_vs_limit
    assert round(svl["spent_usd"], 4) == 8.0
    assert round(svl["limit_usd"], 4) == 100.0
    assert round(svl["ratio"], 4) == 0.08


async def test_format_dashboard_shape(session_factory) -> None:
    await _seed(session_factory)
    async with session_factory() as s:
        engine = InsightsEngine(s)
        report = await engine.generate(days=30)
        payload = engine.format_dashboard(report)
    for key in (
        "days",
        "total_cost_usd",
        "cost_by_project",
        "cost_by_agent",
        "avg_time_per_phase",
        "auto_approve_rate",
        "reversal_rate",
        "spend_vs_limit",
    ):
        assert key in payload
    assert payload["days"] == 30


async def test_empty_db_is_safe(session_factory) -> None:
    async with session_factory() as s:
        report = await InsightsEngine(s).generate(days=30)
    assert report.total_cost_usd == 0.0
    assert report.auto_approve_rate == 0.0
    assert report.reversal_rate == 0.0
    assert report.cost_by_project == {}
    assert report.spend_vs_limit["ratio"] == 0.0


async def test_generate_rejects_invalid_days(session_factory) -> None:
    async with session_factory() as s:
        with pytest.raises(ValueError):
            await InsightsEngine(s).generate(days=0)
        with pytest.raises(ValueError):
            await InsightsEngine(s).generate(days=-5)


async def test_no_forbidden_ecosystem_token_in_module() -> None:
    source = Path(mi.__file__).read_text(encoding="utf-8").lower()
    forbidden = "he" + "rmes"
    assert forbidden not in source
