"""Schemas Pydantic para a API de agentes declarativos (Item A)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentBase(BaseModel):
    name: str = Field(..., description="Nome unico do agente")
    model: str = Field(
        ..., description="Modelo LLM a ser usado (ex: claude-3-5-sonnet)"
    )
    system_prompt: str = Field(
        ..., description="Prompt do sistema que define o comportamento base"
    )
    allowed_tools: List[str] = Field(
        default_factory=list, description="Ferramentas que o agente pode usar"
    )
    max_tokens_budget: float = Field(
        ..., description="Orcamento maximo em tokens (USD) para este agente"
    )

    @field_validator("name")
    @classmethod
    def _no_spaces(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Agent name cannot contain spaces")
        return v


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    max_tokens_budget: Optional[float] = None


class AgentResponse(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
