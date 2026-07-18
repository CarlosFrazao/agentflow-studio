"""Testes dos endpoints do grafo de preferências (Fase D1 / F-010 §5).

Cobre GET /preferences/graph, PATCH (edit), DELETE (archive recuperável) e
POST /restore, além de ownership (404 quando a preferência não pertence ao user).
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


async def _register(client, email="graphapi@example.com"):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "T3st!Pass9", "display_name": "G"},
    )
    return resp.json()["data"]["user"]["id"]


async def _add_pref(client, uid, attribute, value, session_factory):
    await _login_as(client, uid, session_factory)
    resp = await client.post(
        f"{API}/users/{uid}/preferences",
        json={"attribute": attribute, "value": value},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_get_graph_returns_nodes_edges_stats(client, session_factory):
    uid = await _register(client)
    await _login_as(client, uid, session_factory)
    await _add_pref(client, uid, "language", "pt-BR", session_factory)
    await _add_pref(client, uid, "language", "en-US", session_factory)

    resp = await client.get(f"{API}/users/{uid}/preferences/graph")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert set(body.keys()) >= {"nodes", "edges", "stats"}
    assert body["stats"]["nodes"] == 2
    # co-ocorrência do mesmo atributo gera ao menos 1 aresta
    assert body["stats"]["edges"] >= 1


async def test_get_graph_unknown_user_404(client):
    resp = await client.get(
        f"{API}/users/00000000-0000-0000-0000-000000000000/preferences/graph"
    )
    assert resp.status_code == 404


async def test_edit_preference_rewrites_value(client, session_factory):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR", session_factory)
    pid = pref["id"]
    await _login_as(client, uid, session_factory)

    resp = await client.patch(
        f"{API}/users/{uid}/preferences/{pid}",
        json={"value": "pt-BR formal"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["value"] == "pt-BR formal"
    assert resp.json()["data"]["archived"] is False


async def test_archive_preference_sets_archived_flag(client, session_factory):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR", session_factory)
    pid = pref["id"]
    await _login_as(client, uid, session_factory)

    resp = await client.delete(f"{API}/users/{uid}/preferences/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["archived"] is True

    # histórico preservado (ainda listável) — confirma recuperável
    listed = await client.get(f"{API}/users/{uid}/preferences")
    assert any(p["id"] == pid and p["archived"] is True for p in listed.json()["data"])


async def test_restore_preference_clears_archived_flag(client, session_factory):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR", session_factory)
    pid = pref["id"]
    await _login_as(client, uid, session_factory)
    await client.delete(f"{API}/users/{uid}/preferences/{pid}")

    resp = await client.post(f"{API}/users/{uid}/preferences/{pid}/restore")
    assert resp.status_code == 200
    assert resp.json()["data"]["archived"] is False


async def test_archive_unknown_preference_404(client, session_factory):
    uid = await _register(client)
    await _login_as(client, uid, session_factory)
    resp = await client.delete(
        f"{API}/users/{uid}/preferences/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


async def test_edit_requires_non_empty_value(client, session_factory):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR", session_factory)
    pid = pref["id"]
    await _login_as(client, uid, session_factory)

    resp = await client.patch(
        f"{API}/users/{uid}/preferences/{pid}",
        json={"value": "   "},
    )
    # 422 (ValidationError do service ou Pydantic min_length) — ambos rejeitam
    assert resp.status_code == 422


async def test_archive_preference_wrong_owner_404(client, session_factory):
    a = await _register(client, "owner-a@example.com")
    b = await _register(client, "owner-b@example.com")
    pref = await _add_pref(client, a, "language", "pt-BR", session_factory)
    pid = pref["id"]

    # loga como B e tenta arquivar a preferencia de A -> ownership negado (404)
    await _login_as(client, b, session_factory)
    resp = await client.delete(f"{API}/users/{b}/preferences/{pid}")
    assert resp.status_code == 404  # ownership negado
