"""Schemas Pydantic de Card (Kanban)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.card import KANBAN_COLUMNS


class CardCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=300)
    column: str = "backlog"
    order_index: int = 0
    confidence_score: float = 0.0
    approval_by: str = "none"
    auto_approved: bool = False
    revert_deadline: datetime | None = None
    meta: dict = Field(default_factory=dict)

    @field_validator("column")
    @classmethod
    def validate_column(cls, v: str) -> str:
        if v not in KANBAN_COLUMNS:
            raise ValueError(f"coluna invalida: {v}")
        return v


class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    column: str | None = None
    order_index: int | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    approval_by: str | None = None
    meta: dict | None = None


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    column: str
    title: str
    order_index: int
    confidence_score: float
    approval_by: str
    auto_approved: bool
    revert_deadline: datetime | None
    meta: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CardListResponse(BaseModel):
    items: list[CardResponse]
