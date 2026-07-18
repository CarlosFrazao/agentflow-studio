"""Endpoint de métricas/insights do Dashboard (Fase C1 / F-013).

Expõe ``GET /api/v1/metrics/insights?days=30`` com o payload agregado do
``InsightsEngine`` (custo por projeto/agente, tempo médio por fase, taxa de
auto-approve e reversão, gasto vs limite — F-011).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_request_id
from app.core.database import get_session
from app.core.responses import success_envelope
from app.models.user import User
from app.services.metrics_insights import DEFAULT_WINDOW_DAYS, InsightsEngine

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/insights", response_model=None)
async def get_insights(
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    days: int = Query(
        default=DEFAULT_WINDOW_DAYS,
        ge=1,
        le=365,
        description="Janela de análise em dias (1..365).",
    ),
) -> dict:
    # Restrito ao tenant do usuário autenticado (evita totais globais).
    engine = InsightsEngine(session, user_id=user.id)
    report = await engine.generate(days=days)
    return success_envelope(
        data=engine.format_dashboard(report),
        request_id=request_id,
    )
