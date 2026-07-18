"""API de BudgetLimit (F-011) — cap de orçamento por usuário.

warning_level: 'ok' (<80%), 'warning' (>=80%), 'blocked' (>=100%).

FEAT-002 (P0, IDOR + fraude financeira): todas as rotas usam o usuario
autenticado (Depends(get_current_user)) como dono. O user_id NUNCA vem do path
— assim um usuario logado so pode ler/editar SEU proprio orcamento (OWASP API1:
Broken Object Level Authorization). Alem disso, current_month_spend_usd e um
campo DERIVADO das Executions e NUNCA e settable pelo cliente (anti-fraude:
impede zerar o gasto e contornar o cap).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_request_id
from app.core.database import get_session
from app.core.responses import success_envelope
from app.models.budget import BudgetLimit
from app.models.user import User
from app.schemas.budget import BudgetResponse, BudgetUpdate

router = APIRouter(prefix="/users", tags=["budget"])

WARNING_RATIO = 0.80


def _warning_level(spend: float, limit: float) -> str:
    if limit <= 0:
        return "blocked"
    ratio = spend / limit
    if ratio >= 1.0:
        return "blocked"
    if ratio >= WARNING_RATIO:
        return "warning"
    return "ok"


async def _get_or_create_budget(user: User, session: AsyncSession) -> BudgetLimit:
    """Devolve o orcamento do usuario autenticado, criando defaults se ausente."""
    budget = await session.scalar(select_budget().where(BudgetLimit.user_id == user.id))
    if not budget:
        budget = BudgetLimit(user_id=user.id)
        session.add(budget)
        await session.commit()
        await session.refresh(budget)
    return budget


@router.get("/{user_id}/budget", response_model=None)
async def get_budget(
    user_id: UUID,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # O user_id do path e IGNORADO por seguranca (FEAT-002): o orcamento e sempre
    # do usuario autenticado. Assim A GET /users/{B}/budget devolve o de A (nunca
    # o de B) — anti-IDOR de leitura.
    budget = await _get_or_create_budget(user, session)
    data = BudgetResponse.model_validate(budget).model_dump(mode="json")
    data["warning_level"] = _warning_level(
        budget.current_month_spend_usd, budget.monthly_limit_usd
    )
    return success_envelope(data=data, request_id=request_id)


@router.put("/{user_id}/budget", response_model=None)
async def update_budget(
    user_id: UUID,
    body: BudgetUpdate,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # user_id do path IGNORADO (FEAT-002). current_month_spend_usd nao existe em
    # BudgetUpdate: e derivado de Executions e NUNCA settable pelo cliente
    # (anti-fraude — impede zerar o gasto e contornar o cap de orcamento).
    budget = await _get_or_create_budget(user, session)
    if body.monthly_limit_usd is not None:
        budget.monthly_limit_usd = body.monthly_limit_usd
    if body.per_project_limit_usd is not None:
        budget.per_project_limit_usd = body.per_project_limit_usd
    await session.commit()
    await session.refresh(budget)
    data = BudgetResponse.model_validate(budget).model_dump(mode="json")
    data["warning_level"] = _warning_level(
        budget.current_month_spend_usd, budget.monthly_limit_usd
    )
    return success_envelope(data=data, request_id=request_id)


def select_budget():
    from sqlalchemy import select

    return select(BudgetLimit)
