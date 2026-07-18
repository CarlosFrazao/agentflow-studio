"""FEAT-004: isolamento de snippets por dono (IDOR) — P0.

Valida que um usuario logado so cria/lista SEUS proprios snippets e que o
campo user_id do corpo/query e IGNORADO (impede spoofing de dono e enumeracao
de snippets alheios).
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


async def _create_snippet(client, title: str, license: str = "MIT") -> dict:
    resp = await client.post(
        f"{API}/snippets",
        json={"title": title, "content": "x", "language": "py", "license": license},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_snippet_cross_user_create_forbidden(client, session_factory):
    a = await _register(client, "feat004-a@example.com")
    b = await _register(client, "feat004-b@example.com")

    # A loga e tenta criar um snippet no nome de B (user_id do body).
    await _login_as(client, a, session_factory)
    resp = await client.post(
        f"{API}/snippets",
        json={
            "user_id": b,
            "title": "fake owner",
            "content": "x",
            "language": "py",
            "license": "MIT",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    # O dono e SEMPRE o usuario autenticado (A), nunca o user_id do body (B).
    assert str(data["user_id"]) == a
    assert str(data["user_id"]) != b


async def test_snippet_cross_user_list_isolated(client, session_factory):
    a = await _register(client, "feat004-list-a@example.com")
    b = await _register(client, "feat004-list-b@example.com")

    # B cria um snippet seu.
    await _login_as(client, b, session_factory)
    await _create_snippet(client, "B snippet")

    # A loga e lista — nao pode ver o snippet de B.
    await _login_as(client, a, session_factory)
    resp = await client.get(f"{API}/snippets")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 0  # isolamento: A nao ve snippets de B


async def test_snippet_own_crud_ok(client, session_factory):
    a = await _register(client, "feat004-own@example.com")
    await _login_as(client, a, session_factory)

    created = await _create_snippet(client, "A snippet")
    assert str(created["user_id"]) == a

    resp = await client.get(f"{API}/snippets")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
