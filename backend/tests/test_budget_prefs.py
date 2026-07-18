"""Testes dos endpoints /users/{id}/budget e /preferences (Item 5 — cobertura).

Usa o fixture `client`. Registra um usuário para obter um user_id válido.
"""

import pytest
from uuid import UUID

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _login_as(client, user_id: str, session_factory) -> None:
    """Sobrescreve get_current_user para o usuario informado (path e ignorado)."""
    from app.api.v1.deps import get_current_user
    from app.models.user import User

    async with session_factory() as s:
        db_user = await s.get(User, UUID(user_id))
        assert db_user is not None

        async def override() -> User:
            return db_user

    client._transport.app.dependency_overrides[get_current_user] = override


async def _register_and_get_id(client):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "budget@example.com", "password": "T3st!Pass9", "display_name": "B"},
    )
    return resp.json()["data"]["user"]["id"]


async def test_get_budget_creates_default(client, session_factory):
    uid = await _register_and_get_id(client)
    await _login_as(client, uid, session_factory)
    resp = await client.get(f"{API}/users/{uid}/budget")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["warning_level"] in ("ok", "warning", "blocked")


async def test_update_budget_sets_limit_and_level(client, session_factory):
    # FEAT-002: current_month_spend_usd NAO e mais settable; o spend permanece 0
    # (default), entao com limite 100 e gasto 0 o nivel e "ok".
    uid = await _register_and_get_id(client)
    await _login_as(client, uid, session_factory)
    resp = await client.put(
        f"{API}/users/{uid}/budget",
        json={"monthly_limit_usd": 100.0},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["monthly_limit_usd"] == 100.0
    assert data["current_month_spend_usd"] == 0.0
    assert data["warning_level"] == "ok"


async def test_get_budget_requires_auth(anon_client):
    # FEAT-002: sem token o get_current_user levanta 401. O user_id do path e
    # irrelevante (ignorado) — a autenticacao e obrigatoria antes de tudo.
    # Usa anon_client (sem bypass de auth) para exercitar a guarda real.
    resp = await anon_client.get(
        f"{API}/users/00000000-0000-0000-0000-000000000000/budget"
    )
    assert resp.status_code == 401


async def test_preferences_reinforce_and_list(client, session_factory):
    uid = await _register_and_get_id(client)
    await _login_as(client, uid, session_factory)
    reinforce = await client.post(
        f"{API}/users/{uid}/preferences",
        json={"attribute": "language", "value": "pt-BR"},
    )
    assert reinforce.status_code == 201
    body = reinforce.json()["data"]
    assert body["attribute"] == "language"
    # Com 1 reforço, ainda não aplicado (threshold 2)
    assert body["applied"] is False
    listed = await client.get(f"{API}/users/{uid}/preferences")
    assert listed.status_code == 200
    assert any(p["attribute"] == "language" for p in listed.json()["data"])


async def test_preferences_unknown_user_404(client):
    # No POST o user_id do path e IGNORADO (FEAT-001): cria para o usuario logado.
    # O 404 de "usuario desconhecido" aplica-se as rotas de leitura/owner:
    # GET num path que nao e o do usuario logado retorna 404.
    resp = await client.get(
        f"{API}/users/00000000-0000-0000-0000-000000000000/preferences"
    )
    assert resp.status_code == 404
