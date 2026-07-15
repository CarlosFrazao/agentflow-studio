"""Utilitários de segurança: hashing de senha e JWT (auth v1.2).

- Senhas: bcrypt via passlib (lento de propósito, resistente a rainbow tables).
- JWT: HS256 com secret da config; subject = user id (UUID em string).
- create_access_token aceita ttl negativo para facilitar testes de expiração.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Gera o hash bcrypt da senha (nunca armazene a senha em texto puro)."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica a senha contra o hash. Retorna False se o hash for vazio."""
    if not password_hash:
        return False
    return _pwd_context.verify(password, password_hash)


def create_access_token(subject: str | UUID, ttl_minutes: int | None = None) -> str:
    """Cria um JWT HS256 cujo `sub` é o user id.

    ttl_minutes=None usa settings.access_token_ttl_minutes; valores negativos
    geram token já expirado (usado nos testes de guarda).
    """
    ttl = settings.access_token_ttl_minutes if ttl_minutes is None else ttl_minutes
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=ttl)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Decodifica o JWT e retorna o `sub` (user id) ou None se inválido/expirado."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub or payload.get("type") != "access":
        return None
    return str(sub)


def create_refresh_token(subject: str | UUID, ttl_days: int | None = None) -> str:
    """Cria um JWT HS256 do tipo `refresh` (rotação de sessão).

    ttl_days=None usa settings.refresh_token_ttl_days. Vida longa: permite
    renovar o access token sem novo login.
    """
    ttl = settings.refresh_token_ttl_days if ttl_days is None else ttl_days
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=ttl)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_refresh_token(token: str) -> str | None:
    """Decodifica o refresh token e retorna o `sub` ou None se inválido/expirado."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub or payload.get("type") != "refresh":
        return None
    return str(sub)
