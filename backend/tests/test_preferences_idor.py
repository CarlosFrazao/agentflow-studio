"""FEAT-001: isolamento de preferencias por dono (IDOR, P0).

Valida que um usuario logado so pode ler/escrever SUAS proprias preferencias.
Antes da correcao, qualquer usuario logado podia acessar o path /users/{B}/preferences
de outro usuario (Broken Object Level Authorization).
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register(client, email: str) -> str:
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "T3st!Pass9", "display_name": "U"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["user"]["id"]


async def _login_as(client, user_id: str, session_factory) -> None:
    """Sobrescreve get_current_user para o usuario dono do user_id informado."""
    from uuid import UUID

    from app.api.v1.deps import get_current_user
    from app.models.user import User

    async with session_factory() as s:
        db_user = await s.get(User, UUID(user_id))
        assert db_user is not None

        async def override() -> User:
            return db_user

    app = client._transport.app  # ASGITransport expoe o app aqui
    app.dependency_overrides[get_current_user] = override


async def _add_pref(client, uid: str, attribute: str, value: str,
                    session_factory) -> dict:
    await _login_as(client, uid, session_factory)
    resp = await client.post(
        f"{API}/users/{uid}/preferences",
        json={"attribute": attribute, "value": value},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_preferences_cross_user_read_forbidden(client, session_factory):
    a = await _register(client, "feat001-a@example.com")
    b = await _register(client, "feat001-b@example.com")
    await _add_pref(client, b, "language", "pt-BR", session_factory)  # B possui

    # Logamos como A e tentamos LER as preferencias de B
    await _login_as(client, a, session_factory)
    resp = await client.get(f"{API}/users/{b}/preferences")
    assert resp.status_code == 404  # ownership negado, sem vazar existencia


async def test_preferences_cross_user_write_ignored(client, session_factory):
    a = await _register(client, "feat001-wa@example.com")
    b = await _register(client, "feat001-wb@example.com")

    # Logamos como A e tentamos ESCREVER na conta de B
    await _login_as(client, a, session_factory)
    resp = await client.post(
        f"{API}/users/{b}/preferences",
        json={"attribute": "theme", "value": "dark"},
    )
    assert resp.status_code == 201, resp.text
    # A preferencia foi criada para A (usuario logado), nao para B
    data = resp.json()["data"]
    assert str(data["user_id"]) == a

    # Confirmacao: B continua sem preferencias
    await _login_as(client, b, session_factory)
    b_list = await client.get(f"{API}/users/{b}/preferences")
    assert b_list.status_code == 200
    assert b_list.json()["data"] == []


async def test_preferences_own_roundtrip(client, session_factory):
    a = await _register(client, "feat001-own@example.com")
    created = await _add_pref(client, a, "language", "pt-BR", session_factory)
    assert str(created["user_id"]) == a

    await _login_as(client, a, session_factory)
    listed = await client.get(f"{API}/users/{a}/preferences")
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert any(p["id"] == created["id"] for p in items)
