"""Testes do fluxo de autenticação (Item 5 — cobertura de auth.py/users.py)."""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register(client, email="authflow@example.com", pwd="T3st!Pass9"):
    return await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": pwd, "display_name": "A"},
    )


async def test_register_returns_tokens(client):
    resp = await _register(client)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert "access_token" in data and "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_returns_409(client):
    await _register(client, email="dup@example.com")
    resp = await _register(client, email="dup@example.com")
    assert resp.status_code == 409


async def test_login_with_valid_credentials(client):
    await _register(client, email="login@example.com", pwd="Right!Pass1")
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "login@example.com", "password": "Right!Pass1"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


async def test_login_wrong_password_returns_401(client):
    await _register(client, email="wrong@example.com", pwd="Correct!1")
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "wrong@example.com", "password": "errada"},
    )
    assert resp.status_code == 401


async def test_refresh_with_valid_token(client):
    reg = await _register(client, email="refresh@example.com")
    refresh = reg.json()["data"]["refresh_token"]
    resp = await client.post(
        f"{API}/auth/refresh", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


async def test_refresh_with_invalid_token_returns_401(client):
    resp = await client.post(
        f"{API}/auth/refresh", headers={"Authorization": "Bearer token-invalido"}
    )
    assert resp.status_code == 401
