"""Schemas de Snippet (F-009) — licença obrigatória."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.snippet import SNIPPET_LICENSES


class SnippetCreate(BaseModel):
    user_id: UUID
    title: str = Field(min_length=1, max_length=200)
    content: str
    language: str = "text"
    license: str  # obrigatório (F-009)
    source_url: str | None = None

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        if v not in SNIPPET_LICENSES:
            raise ValueError(f"licenca invalida: {v}")
        return v


class SnippetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    content: str
    language: str
    license: str
    source_url: str | None
    created_at: datetime
