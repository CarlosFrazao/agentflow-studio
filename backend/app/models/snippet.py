"""Snippet — biblioteca de trechos reutilizáveis (F-009) com licença obrigatória."""

from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk

SNIPPET_LICENSES = (
    "MIT",
    "Apache-2.0",
    "BSD",
    "GPL",
    "AGPL",
    "unknown",
    "proprietary",
)


class Snippet(Base, TimestampMixin):
    __tablename__ = "snippets"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="text")
    license: Mapped[str] = mapped_column(
        Enum(*SNIPPET_LICENSES, name="snippet_license"), default="unknown", nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
