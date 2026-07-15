"""UserPreference — perfil de preferências aprendido (F-010).

Só é aplicado quando confidence_count >= 2 (evita overfitting em 1 evento).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    attribute: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_reinforced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
