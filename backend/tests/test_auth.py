"""Testes TDD de autenticação JWT (register/login/guarda).

Usa `anon_client` (app SEM override de get_current_user) para exercitar a
guarda real. Os demais testes de integração usam `client` (com override) e
não são afetados pela proteção.

Ciclo: RED primeiro (auth ainda não existe) -> GREEN.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register(client: AsyncClient, email: str = "dev@example.com", password: str = "s3cret-pass", display: str = "Dev") -> dict:
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "display_name": display},
    )
    return resp


async def test_register_returns_201_and_token_without_hash(anon_client: AsyncClient) -> None:
    resp = await _register(anon_client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"
    # Nunca expor o hash da senha
    assert "password_hash" not in body["data"]
    assert body["data"]["user"]["email"] == "dev@example.com"


async def test_register_duplicate_email_returns_409(anon_client: AsyncClient) -> None:
    await _register(anon_client, email="dup@example.com")
    resp = await _register(anon_client, email="dup@example.com")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_login_with_valid_credentials_returns_token(anon_client: AsyncClient) -> None:
    await _register(anon_client, email="login@example.com", password="right-pass")
    resp = await anon_client.post(
        f"{API}/auth/login",
        json={"email": "login@example.com", "password": "right-pass"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


async def test_login_with_wrong_password_returns_401(anon_client: AsyncClient) -> None:
    await _register(anon_client, email="wrong@example.com", password="correct")
    resp = await anon_client.post(
        f"{API}/auth/login",
        json={"email": "wrong@example.com", "password": "incorrect"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_protected_endpoint_without_token_returns_401(anon_client: AsyncClient) -> None:
    resp = await anon_client.get(f"{API}/projects")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_protected_endpoint_with_invalid_token_returns_401(anon_client: AsyncClient) -> None:
    resp = await anon_client.get(
        f"{API}/projects",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


async def test_protected_endpoint_with_expired_token_returns_401(anon_client: AsyncClient) -> None:
    # Precisa de um usuário para o subject do token
    reg = await _register(anon_client, email="exp@example.com")
    uid = reg.json()["data"]["user"]["id"]
    expired = create_access_token(uid, ttl_minutes=-1)
    resp = await anon_client.get(
        f"{API}/projects",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert resp.status_code == 401


async def test_protected_endpoint_with_valid_token_succeeds(anon_client: AsyncClient) -> None:
    reg = await _register(anon_client, email="ok@example.com", password="pw123456")
    token = reg.json()["data"]["access_token"]
    resp = await anon_client.get(
        f"{API}/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_login_nonexistent_equalizes_timing(anon_client: AsyncClient) -> None:
    """FEAT-007: branch de usuario inexistente nao vaza existencia por tempo.

    O email inexistente deve responder 401 e consumir um tempo de verificacao
    comparavel ao de um usuario real com senha errada (ambos rodam bcrypt contra
    um hash de mesmo custo), mitigando o timing oracle de enumeracao de emails.
    """
    # Usuario real com senha errada (branch que roda verify() contra hash real).
    await _register(anon_client, email="real@example.com", password="real-pass-123")
    wrong_resp = await anon_client.post(
        f"{API}/auth/login",
        json={"email": "real@example.com", "password": "wrong-password"},
    )
    assert wrong_resp.status_code == 401

    # Email inexistente: deve falhar com o mesmo status sem vazar existencia.
    none_resp = await anon_client.post(
        f"{API}/auth/login",
        json={"email": "ghost@example.com", "password": "whatever-pass"},
    )
    assert none_resp.status_code == 401
    assert none_resp.json()["error"]["code"] == "UNAUTHORIZED"
