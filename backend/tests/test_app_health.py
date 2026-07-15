"""Smoke test de boot da aplicação e do endpoint /health com envelope padrão."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def test_health_returns_standard_envelope(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["meta"]["request_id"]
    assert "timestamp" in body["meta"]


async def test_docs_available_in_debug(client: AsyncClient) -> None:
    resp = await client.get("/docs")
    assert resp.status_code == 200
