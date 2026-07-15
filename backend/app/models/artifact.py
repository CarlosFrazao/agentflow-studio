"""Artifact — saída dos agentes (markdown/json/code) anexada a um card."""

from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk

ARTIFACT_TYPES = ("markdown", "json", "code")


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"

    id: Mapped[UUID] = uuid_pk()
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum(*ARTIFACT_TYPES, name="artifact_type"), default="markdown", nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
