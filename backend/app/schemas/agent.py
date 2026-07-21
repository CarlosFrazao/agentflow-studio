"""Schemas Pydantic para a API de agentes declarativos (Item A)."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Known tool catalog (B4-2 defense-in-depth): an agent may only declare tools
# from this allow-list. Unknown tool names are rejected at the schema boundary,
# preventing a stored/forwarded agent definition from requesting capabilities
# outside the supported sandbox surface.
ALLOWED_TOOLS_CATALOG: frozenset[str] = frozenset(
    {
        "read_file",
        "write_file",
        "edit_file",
        "list_dir",
        "run_test",
        "exec_command",
        "web_search",
        "web_scrape",
        "github_read",
        "github_write",
        "sra_research",
        "vector_search",
        "shell_exec",
    }
)


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

    @field_validator("allowed_tools")
    @classmethod
    def _known_tools_only(cls, v: List[str]) -> List[str]:
        if not v:
            return v
        unknown = [t for t in v if t not in ALLOWED_TOOLS_CATALOG]
        if unknown:
            raise ValueError(
                f"Unknown tool(s) not in allow-list: {', '.join(sorted(unknown))}"
            )
        # Reject duplicates (defense-in-depth: a tool listed twice is a typo).
        if len(v) != len(set(v)):
            raise ValueError("allowed_tools contains duplicates")
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
    user_id: UUID | None
    created_at: datetime
    updated_at: datetime
