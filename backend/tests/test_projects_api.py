"""Testes TDD da API de Projects (CRUD + envelope padronizado)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_project_returns_201_with_envelope(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/projects", json={"name": "App de Receitas", "description": "MVP"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert "id" in body["data"]
    assert body["data"]["name"] == "App de Receitas"
    assert isinstance(body["meta"]["request_id"], str)
    assert body["meta"]["request_id"]


async def test_get_project_by_id(client: AsyncClient) -> None:
    created = await client.post("/api/v1/projects", json={"name": "Projeto X"})
    pid = created.json()["data"]["id"]
    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == pid


async def test_get_missing_project_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["success"] is False
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_patch_project_updates_fields(client: AsyncClient) -> None:
    created = await client.post("/api/v1/projects", json={"name": "Original"})
    pid = created.json()["data"]["id"]
    resp = await client.patch(
        f"/api/v1/projects/{pid}", json={"description": "Atualizado"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "Atualizado"


async def test_delete_project_returns_204(client: AsyncClient) -> None:
    created = await client.post("/api/v1/projects", json={"name": "Para deletar"})
    pid = created.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/projects/{pid}")).status_code == 404


async def test_list_projects_has_pagination_meta(client: AsyncClient) -> None:
    for i in range(3):
        await client.post("/api/v1/projects", json={"name": f"P{i}"})
    resp = await client.get("/api/v1/projects?page=1&per_page=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["pagination"]["total"] == 3
    assert body["meta"]["pagination"]["total_pages"] == 2
