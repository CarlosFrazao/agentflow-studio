"""Schemas Pydantic de Artifact."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreate(BaseModel):
    agent_name: str = Field(min_length=1, max_length=100)
    type: str = "markdown"  # markdown | json | code
    content: str


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    card_id: UUID
    agent_name: str
    type: str
    content: str
    created_at: datetime
