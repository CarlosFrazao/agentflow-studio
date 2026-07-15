"""Schemas de BudgetLimit (F-011) — cap de orçamento."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BudgetUpdate(BaseModel):
    monthly_limit_usd: float | None = Field(default=None, ge=0)
    per_project_limit_usd: float | None = Field(default=None, ge=0)
    current_month_spend_usd: float | None = Field(default=None, ge=0)


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    monthly_limit_usd: float
    per_project_limit_usd: float
    current_month_spend_usd: float
    warning_level: str = ""  # ok | warning (>=80%) | blocked (>=100%)
    updated_at: datetime
