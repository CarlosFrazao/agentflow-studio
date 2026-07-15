"""Modelo ORM de Agentes declarativos (Item A do analise_omnigent.md).

Persiste definições de agentes customizados (YAML/JSON) no SQLite para que
o usuário possa registrar novos agentes sem alterar o código.
"""

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin


class Agent(Base, TimestampMixin):
    """Agente declarativo configurável pelo usuário."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    system_prompt: Mapped[str] = mapped_column(String, nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    max_tokens_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
