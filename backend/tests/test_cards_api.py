"""Testes TDD da API de Cards (Kanban) — criar, listar, mover coluna, deletar."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_project(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/projects", json={"name": "Base"})
    return resp.json()["data"]["id"]


async def test_create_card_returns_201(client: AsyncClient) -> None:
    pid = await _create_project(client)
    resp = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Ideia A"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["title"] == "Ideia A"
    assert body["data"]["column"] == "backlog"


async def test_create_card_without_project_returns_422(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/cards", json={"title": "Orfao"})
    assert resp.status_code == 422


async def test_list_cards_filters_by_column(client: AsyncClient) -> None:
    pid = await _create_project(client)
    await client.post("/api/v1/cards", json={"project_id": pid, "title": "A"})
    await client.post("/api/v1/cards", json={"project_id": pid, "title": "B"})

    resp = await client.get(f"/api/v1/cards?project_id={pid}&column=backlog")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2

    # coluna sem cards
    resp = await client.get(f"/api/v1/cards?project_id={pid}&column=done")
    assert len(resp.json()["data"]) == 0


async def test_get_card_by_id_and_404(client: AsyncClient) -> None:
    pid = await _create_project(client)
    created = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "C"}
    )
    cid = created.json()["data"]["id"]
    assert (await client.get(f"/api/v1/cards/{cid}")).status_code == 200
    assert (
        await client.get("/api/v1/cards/00000000-0000-0000-0000-000000000000")
    ).status_code == 404


async def test_move_card_to_another_column(client: AsyncClient) -> None:
    pid = await _create_project(client)
    created = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "D"}
    )
    cid = created.json()["data"]["id"]
    resp = await client.patch(f"/api/v1/cards/{cid}", json={"column": "researching"})
    assert resp.status_code == 200
    assert resp.json()["data"]["column"] == "researching"


async def test_patch_card_invalid_column_returns_422(client: AsyncClient) -> None:
    pid = await _create_project(client)
    created = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "E"}
    )
    cid = created.json()["data"]["id"]
    resp = await client.patch(f"/api/v1/cards/{cid}", json={"column": "voando"})
    assert resp.status_code == 422


async def test_delete_card_returns_204(client: AsyncClient) -> None:
    pid = await _create_project(client)
    created = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "F"}
    )
    cid = created.json()["data"]["id"]
    assert (await client.delete(f"/api/v1/cards/{cid}")).status_code == 204
    assert (await client.get(f"/api/v1/cards/{cid}")).status_code == 404
