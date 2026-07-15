"""Execution — métricas de tempo/custo por execução de agente."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk

EXECUTION_STATUS = ("pending", "running", "success", "failed")


class Execution(Base, TimestampMixin):
    __tablename__ = "executions"

    id: Mapped[UUID] = uuid_pk()
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*EXECUTION_STATUS, name="execution_status"),
        default="pending",
        nullable=False,
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
