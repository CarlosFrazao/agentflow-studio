"""BudgetLimit — cap de orçamento por usuário (F-011)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class BudgetLimit(Base):
    __tablename__ = "budget_limits"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    monthly_limit_usd: Mapped[float] = mapped_column(
        Float, default=10.0, nullable=False
    )
    per_project_limit_usd: Mapped[float] = mapped_column(
        Float, default=3.0, nullable=False
    )
    current_month_spend_usd: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
