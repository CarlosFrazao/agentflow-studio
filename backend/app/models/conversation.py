"""Conversation + Message — estado da Orquestração Conversacional (F-023 Conductor).

Cada `Conversation` é atrelada a um `Project` (e opcionalmente a um `Card` que o
Conductor cria/avança). Cada `Message` é um turno: `user` (entrada), `conductor`
(resposta narrativa consolidada) ou `tool` (execução transparente de um agente).

Respeita Base + TimestampMixin (uuid_pk, created_at, updated_at prontos).
"""

from uuid import UUID

from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk

# Papéis de mensagem no chat do Conductor.
MSG_ROLES = ("user", "conductor", "tool")


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[UUID] = uuid_pk()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    card_id: Mapped[UUID | None] = mapped_column(ForeignKey("cards.id"), nullable=True)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Enum(*MSG_ROLES, name="msg_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    tool_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tool_input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
