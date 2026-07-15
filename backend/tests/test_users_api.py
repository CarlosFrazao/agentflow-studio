"""Testes TDD da API de Users (MVP single-tenant, sem auth ainda)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_user_returns_201(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/users",
        json={"email": "dev@example.com", "display_name": "Dev"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == "dev@example.com"
    assert "id" in body["data"]


async def test_get_user_by_id_and_404(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/users", json={"email": "a@b.com", "display_name": "A"}
    )
    uid = created.json()["data"]["id"]
    assert (await client.get(f"/api/v1/users/{uid}")).status_code == 200
    assert (
        await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
    ).status_code == 404
