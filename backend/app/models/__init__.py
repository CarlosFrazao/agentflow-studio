"""Agregador de modelos — importa todos para registrar no metadata do Base.

Mantém Base.metadata completo para create_all / Alembic autogenerate.
"""

from app.models.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.card import Card  # noqa: F401
from app.models.artifact import Artifact  # noqa: F401
from app.models.execution import Execution  # noqa: F401
from app.models.snippet import Snippet  # noqa: F401
from app.models.user_preference import UserPreference  # noqa: F401
from app.models.budget import BudgetLimit  # noqa: F401
from app.models.research_cache import ResearchCache  # noqa: F401
from app.models.agent import Agent  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Project",
    "Card",
    "Artifact",
    "Execution",
    "Snippet",
    "UserPreference",
    "BudgetLimit",
    "ResearchCache",
    "Agent",
    "Conversation",
    "Message",
]
