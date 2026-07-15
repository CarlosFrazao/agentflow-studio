"""ResearchCache — evita rechamar SRA/Firecrawl para query similar (F-003/F-008)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk

CACHE_SOURCE = ("sra", "code_research")

CACHE_TTL_DAYS = 7


class ResearchCache(Base):
    __tablename__ = "research_cache"

    id: Mapped[UUID] = uuid_pk()
    query_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(
        Enum(*CACHE_SOURCE, name="cache_source"), nullable=False
    )
    result: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
