"""Testes dos endpoints do grafo de preferências (Fase D1 / F-010 §5).

Cobre GET /preferences/graph, PATCH (edit), DELETE (archive recuperável) e
POST /restore, além de ownership (404 quando a preferência não pertence ao user).
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register(client, email="graphapi@example.com"):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "T3st!Pass9", "display_name": "G"},
    )
    return resp.json()["data"]["user"]["id"]


async def _add_pref(client, uid, attribute, value):
    resp = await client.post(
        f"{API}/users/{uid}/preferences",
        json={"attribute": attribute, "value": value},
    )
    return resp.json()["data"]


async def test_get_graph_returns_nodes_edges_stats(client):
    uid = await _register(client)
    await _add_pref(client, uid, "language", "pt-BR")
    await _add_pref(client, uid, "language", "en-US")  # mesmo atributo → co-ocorrência

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


async def test_edit_preference_rewrites_value(client):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR")
    pid = pref["id"]

    resp = await client.patch(
        f"{API}/users/{uid}/preferences/{pid}",
        json={"value": "pt-BR formal"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["value"] == "pt-BR formal"
    assert resp.json()["data"]["archived"] is False


async def test_archive_preference_sets_archived_flag(client):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR")
    pid = pref["id"]

    resp = await client.delete(f"{API}/users/{uid}/preferences/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["archived"] is True

    # histórico preservado (ainda listável) — confirma recuperável
    listed = await client.get(f"{API}/users/{uid}/preferences")
    assert any(p["id"] == pid and p["archived"] is True for p in listed.json()["data"])


async def test_restore_preference_clears_archived_flag(client):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR")
    pid = pref["id"]
    await client.delete(f"{API}/users/{uid}/preferences/{pid}")

    resp = await client.post(f"{API}/users/{uid}/preferences/{pid}/restore")
    assert resp.status_code == 200
    assert resp.json()["data"]["archived"] is False


async def test_archive_unknown_preference_404(client):
    uid = await _register(client)
    resp = await client.delete(
        f"{API}/users/{uid}/preferences/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


async def test_edit_requires_non_empty_value(client):
    uid = await _register(client)
    pref = await _add_pref(client, uid, "language", "pt-BR")
    pid = pref["id"]

    resp = await client.patch(
        f"{API}/users/{uid}/preferences/{pid}",
        json={"value": "   "},
    )
    # 422 (ValidationError do service ou Pydantic min_length) — ambos rejeitam
    assert resp.status_code == 422


async def test_archive_preference_wrong_owner_404(client):
    a = await _register(client, "owner-a@example.com")
    b = await _register(client, "owner-b@example.com")
    pref = await _add_pref(client, a, "language", "pt-BR")
    pid = pref["id"]

    # tenta arquivar a preferência de A sob o path do user B
    resp = await client.delete(f"{API}/users/{b}/preferences/{pid}")
    assert resp.status_code == 404  # ownership negado
