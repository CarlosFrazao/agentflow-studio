"""API de autenticação (v1.2): registro, login e emissão de JWT.

Público: /auth/register, /auth/login. Os demais routers da v1 exigem
o Bearer token via get_current_user (ver app/api/v1/deps.py).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.exceptions import ConflictError, UnauthorizedError
from app.api.v1.deps import get_current_user_id, get_request_id
from app.core.responses import success_envelope
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_against_dummy,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import AuthLogin, AuthRegister, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "af_token"


def _set_auth_cookie(response: Response, token: str) -> None:
    """Grava o access token num cookie HttpOnly (FEAT-008 / B10-1).

    HttpOnly => inacessível a ``document.cookie`` (mitiga roubo de sessão via
    XSS). SameSite=Strict evita envio em navegações cross-site (CSRF). Secure é
    ligado só em produção (localhost é http, onde Secure impediria o cookie).
    """
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=settings.is_production,
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    """Expira o cookie de auth (logout)."""
    response.delete_cookie(COOKIE_NAME, path="/")


def _issue_tokens(user: User) -> dict:
    """Monta o envelope de tokens (access + refresh) para um usuário."""
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "expires_in_minutes": _ttl(),
        "user": UserPublic.model_validate(user).model_dump(mode="json"),
    }


@router.post("/register", response_model=None, status_code=status.HTTP_201_CREATED)
async def register(
    body: AuthRegister,
    response: Response,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing:
        raise ConflictError("email ja cadastrado")

    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    tokens = _issue_tokens(user)
    _set_auth_cookie(response, tokens["access_token"])
    return success_envelope(data=tokens, request_id=request_id)


@router.post("/login", response_model=None)
async def login(
    body: AuthLogin,
    response: Response,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await session.scalar(select(User).where(User.email == body.email))
    # Mitiga timing oracle de forma completa (Audit BUG-001): independente de o
    # usuario existir, SEMPRE roda um verify() de custo constante contra o hash
    # real (se existir) OU contra o dummy. Assim a latencia da rota de login e
    # identica para emails validos e invalidos, impedindo enumeracao por tempo.
    if user is not None:
        password_ok = verify_password(body.password, user.password_hash)
    else:
        password_ok = verify_against_dummy(body.password)

    if not password_ok:
        raise UnauthorizedError("credenciais invalidas")

    tokens = _issue_tokens(user)
    _set_auth_cookie(response, tokens["access_token"])
    return success_envelope(data=tokens, request_id=request_id)


@router.post("/refresh", response_model=None)
async def refresh(
    request: Request,
    response: Response,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Renova o access token a partir de um refresh token válido (rotação)."""

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise UnauthorizedError("token de acesso ausente")
    refresh_token = header[len("Bearer ") :].strip()
    user_id = decode_refresh_token(refresh_token)
    if user_id is None:
        raise UnauthorizedError("refresh token invalido ou expirado")

    user = await session.get(User, UUID(user_id))
    if user is None:
        raise UnauthorizedError("usuario nao encontrado")

    tokens = _issue_tokens(user)
    _set_auth_cookie(response, tokens["access_token"])
    return success_envelope(data=tokens, request_id=request_id)


@router.post("/logout", response_model=None)
async def logout(
    response: Response,
    request_id: str = Depends(get_request_id),
) -> dict:
    """FEAT-008: expira o cookie HttpOnly de auth (logout do lado do cliente).

    O access token fica em memória no frontend; ao limpar o cookie o backend
    deixa de aceitar a sessão via cookie. O token ainda é válido até expirar
    se enviado via Bearer, mas o cliente descarta o token em memória no logout.
    """
    _clear_auth_cookie(response)
    return success_envelope(data={"logged_out": True}, request_id=request_id)


def _ttl() -> int:
    return get_settings().access_token_ttl_minutes
