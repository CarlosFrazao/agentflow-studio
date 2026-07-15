"""Testes unitários de segurança (Item 5 — cobertura).

Cobrem refresh tokens e decode de access token (lógica pura).
"""

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


def test_access_token_roundtrip() -> None:
    tok = create_access_token("user-123")
    assert decode_access_token(tok) == "user-123"


def test_access_token_invalid_returns_none() -> None:
    assert decode_access_token("not-a-real-token") is None


def test_refresh_token_roundtrip_and_type() -> None:
    tok = create_refresh_token("user-456", ttl_days=7)
    assert decode_refresh_token(tok) == "user-456"
    # access token não deve ser aceito como refresh
    access = create_access_token("user-456")
    assert decode_refresh_token(access) is None


def test_password_hash_and_verify() -> None:
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_empty_hash() -> None:
    assert verify_password("x", "") is False
