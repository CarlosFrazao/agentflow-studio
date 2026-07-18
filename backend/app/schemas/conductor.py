"""Schemas Pydantic da Orquestração Conversacional (F-023 Conductor)."""

from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    project_id: UUID


class ConversationResponse(BaseModel):
    id: UUID
    project_id: UUID
    card_id: UUID | None = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str = ""
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None


class ConversationMessagesResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class ConductorTurnRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


class ConductorToolCall(BaseModel):
    tool: str
    input: dict = Field(default_factory=dict)
    output: dict | None = None


class ConductorTurnResponse(BaseModel):
    conversation_id: UUID
    conductor_reply: str
    tool_calls: list[ConductorToolCall] = Field(default_factory=list)
    card_id: UUID | None = None
    awaiting_user: bool = False
    awaiting_confirmation: bool = False


# --- Plano emitido pelo LLM (parsing manual de function calling) ---


class _ToolCallIntent(BaseModel):
    tool: str
    input: dict = Field(default_factory=dict)


class ConductorPlan(BaseModel):
    narrative: str = ""
    tool_calls: list[_ToolCallIntent] = Field(default_factory=list)
