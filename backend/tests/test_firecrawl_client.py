"""Testes do FirecrawlClient (Item 5 — cobertura) sem rede.

Foca no fallback REST (/v2/scrape) usando httpx.MockTransport.
O path MCP (SSE) não é exercitado (exigiria servidor SSE real).
"""

import httpx
import pytest

from app.clients.mcp.firecrawl_client import (
    FirecrawlClient,
    FirecrawlUnavailableError,
)
from app.core.config import get_settings

pytestmark = pytest.mark.asyncio


def _rest_client(handler) -> FirecrawlClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = FirecrawlClient(http_client=http_client, clock=lambda: 0.0)
    client.supports_mcp = False  # força fallback REST (sem SSE)
    return client


async def test_scrape_rest_returns_json() -> None:
    def handler(request):
        return httpx.Response(200, json={"markdown": "# oi"})

    client = _rest_client(handler)
    out = await client.scrape("https://ex.com")
    assert out == {"markdown": "# oi"}


async def test_scrape_rest_error_raises() -> None:
    def handler(request):
        return httpx.Response(502, json={"error": "bad gateway"})

    client = _rest_client(handler)
    with pytest.raises(FirecrawlUnavailableError):
        await client.scrape("https://ex.com")


async def test_scrape_breaker_open_raises() -> None:
    settings = get_settings()
    client = FirecrawlClient(settings=settings, clock=lambda: 0.0)
    client.supports_mcp = False
    for _ in range(settings.circuit_breaker_threshold):
        client._breaker.record_failure()
    with pytest.raises(FirecrawlUnavailableError):
        await client.scrape("https://ex.com")

# ---- Retry (http-request-mastery) ----
async def test_scrape_rest_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(502, json={"message": "bad gateway"})
        return httpx.Response(200, json={"data": "ok"})

    client = _rest_client(handler)
    out = await client._scrape_rest("http://example.com", retry_kwargs={"max_attempts": 3, "base_delay": 0.001, "max_delay": 0.002, "jitter_factor": 0})
    assert out["data"] == "ok"
    assert calls["n"] == 3
