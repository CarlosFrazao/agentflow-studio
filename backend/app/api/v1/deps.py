"""Dependencies comuns da API v1."""

import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User


def get_request_id(request: Request) -> str:
    """Lê X-Request-ID do header ou gera um UUID para rastreabilidade."""
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def get_current_user_id(request: Request) -> str:
    """Extrai e valida o Bearer token; retorna o subject (user_id) ou 401."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise UnauthorizedError("token de acesso ausente")
    token = header[len("Bearer ") :].strip()
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
