"""Project — agrupa cards de uma ideia em evolução."""

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[UUID] = uuid_pk()
    # MVP single-tenant (sem auth): opcional. Torna-se obrigatório em v2 (auth/JWT).
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(50), default="active")
