"""Dependencies comuns da API v1."""

import uuid
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.card import Card
from app.models.conversation import Conversation
from app.models.project import Project
from app.models.user import User


def get_request_id(request: Request) -> str:
    """Lê X-Request-ID do header ou gera um UUID para rastreabilidade."""
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def get_current_user_id(request: Request) -> str:
    """Extrai e valida o token de acesso; retorna o subject (user_id) ou 401.

    FEAT-008 (B10-1): aceita o token de duas fontes, nesta ordem:
      1. Header ``Authorization: Bearer <token>`` (usado por WebSockets/agentes
         e por clientes que ainda preferem Bearer).
      2. Cookie ``af_token`` HttpOnly (setado em /auth/login|register|refresh).
         O cookie é inacessível a ``document.cookie``, mitigando roubo de sessão
         via XSS. O fallback mantém compatibilidade com o WS de share, que não
         consegue enviar cookies sozinho e continua usando o token via query.
    """
    header = request.headers.get("Authorization", "")
    token: str | None = None
    if header.startswith("Bearer "):
        token = header[len("Bearer ") :].strip()
    if not token:
        token = request.cookies.get("af_token")
    if not token:
        raise UnauthorizedError("token de acesso ausente")
    user_id = decode_access_token(token)
    if user_id is None:
        raise UnauthorizedError("token invalido ou expirado")
    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Carrega o usuário autenticado; 401 se inexistente."""
    user = await session.get(User, uuid.UUID(user_id))
    if user is None:
        raise UnauthorizedError("usuario nao encontrado")
    return user


# ---------------------------------------------------------------------------
# Authorization (OWASP API1: Broken Object Level Authorization)
# O sistema tem auth JWT multi-usuário ativa, mas os recursos são isolados
# por user_id. Estas dependências garantem que um usuário só acesse/modifique
# recursos que ele de fato possui — sem isso, qualquer usuário logado
# poderia enumerar UUIDs alheios (IDOR).
# ---------------------------------------------------------------------------


async def get_owned_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Project:
    """Devolve o Project se ele pertencer ao usuário; 404 caso contrário.

    404 (e não 403) para não vazar a existência do recurso de outro dono.
    """
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise NotFoundError("Project", str(project_id))
    return project


async def get_owned_card(
    card_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Card:
    """Devolve o Card se o Project pai pertencer ao usuário; 404 c.c.

    Card não tem user_id próprio: herda do Project via project_id. O project
    é eager-loaded (selectinload) para que ``card.project`` já esteja populado
    no corpo da rota sem nova query (evita N+1 em listagens).
    """
    stmt = select(Card).where(Card.id == card_id)
    card = (await session.scalars(stmt)).first()
    if card is None:
        raise NotFoundError("Card", str(card_id))
    project = card.project
    if project is None or project.user_id != user.id:
        raise NotFoundError("Card", str(card_id))
    return card


async def get_owned_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    """Devolve a Conversation se o Project pai pertencer ao usuário; 404 c.c."""
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise NotFoundError("Conversation", str(conversation_id))
    project = await session.get(Project, conv.project_id)
    if project is None or project.user_id != user.id:
        raise NotFoundError("Conversation", str(conversation_id))
    return conv
