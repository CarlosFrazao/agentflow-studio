"""Card — coração do Kanban. Representa uma ideia em evolução no pipeline."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk

KANBAN_COLUMNS = (
    "backlog",
    "researching",
    "planning",
    "reviewing",
    "production",
    "done",
)

APPROVAL_BY = ("human", "auto", "none")


class Card(Base, TimestampMixin):
    __tablename__ = "cards"

    id: Mapped[UUID] = uuid_pk()
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    column: Mapped[str] = mapped_column(
        Enum(*KANBAN_COLUMNS, name="kanban_column"), default="backlog", nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approval_by: Mapped[str] = mapped_column(
        Enum(*APPROVAL_BY, name="approval_by"), default="none", nullable=False
    )
    auto_approved: Mapped[bool] = mapped_column(default=False, nullable=False)
    revert_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Metadados ricos do frontend (code, phase, priority, estimate, agent,
    # description, checklist, deps). Persistidos como JSON para evitar
    # proliferação de colunas no MVP single-tenant.
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
