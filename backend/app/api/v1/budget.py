"""API de BudgetLimit (F-011) — cap de orçamento por usuário.

warning_level: 'ok' (<80%), 'warning' (>=80%), 'blocked' (>=100%).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError
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


@router.get("/{user_id}/budget", response_model=None)
async def get_budget(
    user_id: UUID,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(User, user_id):
        raise NotFoundError("User", str(user_id))
    budget = await session.scalar(
        select_budget().where(BudgetLimit.user_id == user_id)
    )
    if not budget:
        budget = BudgetLimit(user_id=user_id)
        session.add(budget)
        await session.commit()
        await session.refresh(budget)
    data = BudgetResponse.model_validate(budget).model_dump(mode="json")
    data["warning_level"] = _warning_level(
        budget.current_month_spend_usd, budget.monthly_limit_usd
    )
    return success_envelope(data=data, request_id=request_id)


@router.put("/{user_id}/budget", response_model=None)
async def update_budget(
    user_id: UUID,
    body: BudgetUpdate,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(User, user_id):
        raise NotFoundError("User", str(user_id))
    budget = await session.scalar(
        select_budget().where(BudgetLimit.user_id == user_id)
    )
    if not budget:
        budget = BudgetLimit(user_id=user_id)
        session.add(budget)
    if body.monthly_limit_usd is not None:
        budget.monthly_limit_usd = body.monthly_limit_usd
    if body.per_project_limit_usd is not None:
        budget.per_project_limit_usd = body.per_project_limit_usd
    if body.current_month_spend_usd is not None:
        budget.current_month_spend_usd = body.current_month_spend_usd
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
