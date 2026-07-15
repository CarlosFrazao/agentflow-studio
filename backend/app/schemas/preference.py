"""Schemas de UserPreference (F-010)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreferenceCreate(BaseModel):
    attribute: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=300)


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    attribute: str
    value: str
    confidence_count: int
    applied: bool = False  # True quando confidence_count >= 2
    archived: bool = False  # True quando removida (arquivada recuperável)
    last_reinforced_at: datetime


class PreferenceEdit(BaseModel):
    value: str = Field(min_length=1, max_length=300)


class PreferenceGraphResponse(BaseModel):
    """Payload do grafo de preferências (Fase D1) para o frontend desenhar."""

    nodes: list[dict[str, object]]
    edges: list[dict[str, object]]
    stats: dict[str, object]


class PreferenceListResponse(BaseModel):
    items: list[PreferenceResponse]
