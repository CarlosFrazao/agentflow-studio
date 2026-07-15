"""Testes de CRUD dos endpoints /cards e /projects (Item 5 — cobertura).

Usa o fixture `client` (sessão em memória + auth bypass). Sem rede.
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _create_project(client, name="Proj"):
    resp = await client.post(f"{API}/projects", json={"name": name, "description": "d"})
    return resp.json()["data"]["id"]


async def test_create_and_get_project(client):
    pid = await _create_project(client)
    resp = await client.get(f"{API}/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == pid


async def test_get_unknown_project_returns_404(client):
    resp = await client.get(f"{API}/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_create_project_invalid_body_returns_422(client):
    resp = await client.post(f"{API}/projects", json={})
    assert resp.status_code == 422


async def test_patch_project(client):
    pid = await _create_project(client)
    resp = await client.patch(f"{API}/projects/{pid}", json={"name": "Novo"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Novo"


async def test_delete_project(client):
    pid = await _create_project(client)
    resp = await client.delete(f"{API}/projects/{pid}")
    assert resp.status_code == 204
    follow = await client.get(f"{API}/projects/{pid}")
    assert follow.status_code == 404


async def test_create_card_and_list(client):
    pid = await _create_project(client)
    resp = await client.post(
        f"{API}/cards", json={"project_id": pid, "title": "C1", "column": "backlog"}
    )
    assert resp.status_code == 201
    cid = resp.json()["data"]["id"]
    listed = await client.get(f"{API}/cards", params={"project_id": pid})
    assert listed.status_code == 200
    assert any(c["id"] == cid for c in listed.json()["data"])


async def test_create_card_invalid_column_returns_422(client):
    pid = await _create_project(client)
    resp = await client.post(
        f"{API}/cards", json={"project_id": pid, "title": "C", "column": "nao_existe"}
    )
    assert resp.status_code == 422


async def test_get_card_and_404(client):
    pid = await _create_project(client)
    resp = await client.post(
        f"{API}/cards", json={"project_id": pid, "title": "C", "column": "backlog"}
    )
    cid = resp.json()["data"]["id"]
    got = await client.get(f"{API}/cards/{cid}")
    assert got.status_code == 200
    missing = await client.get(f"{API}/cards/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


async def test_patch_card_move_column(client):
    pid = await _create_project(client)
    resp = await client.post(
        f"{API}/cards", json={"project_id": pid, "title": "C", "column": "backlog"}
    )
    cid = resp.json()["data"]["id"]
    patch = await client.patch(f"{API}/cards/{cid}", json={"column": "done"})
    assert patch.status_code == 200
    assert patch.json()["data"]["column"] == "done"


async def test_delete_card(client):
    pid = await _create_project(client)
    resp = await client.post(
        f"{API}/cards", json={"project_id": pid, "title": "C", "column": "backlog"}
    )
    cid = resp.json()["data"]["id"]
    d = await client.delete(f"{API}/cards/{cid}")
    assert d.status_code == 204
