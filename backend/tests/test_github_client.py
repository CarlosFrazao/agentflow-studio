"""Testes do GitHubClient (Item 5 — cobertura) sem rede.

Usa httpx.MockTransport para interceptar chamadas. Valida sucesso,
erro (circuit breaker), e breaker aberto.
"""

import base64

import httpx
import pytest

from app.clients.github_client import GitHubClient, GitHubUnavailableError
from app.core.config import get_settings

pytestmark = pytest.mark.asyncio


def _client_with(handler) -> GitHubClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return GitHubClient(http_client=http_client, clock=lambda: 0.0)


async def test_get_file_decodes_base64() -> None:
    content = base64.b64encode(b"print('oi')").decode()
    body = {"content": content, "encoding": "base64"}

    def handler(request):
        return httpx.Response(200, json=body)

    client = _client_with(handler)
    out = await client.get_file("o/r", "README.md")
    assert "print" in out


async def test_get_file_http_error_raises_github_unavailable() -> None:
    def handler(request):
        return httpx.Response(503, json={"message": "busy"})

    client = _client_with(handler)
    with pytest.raises(GitHubUnavailableError):
        await client.get_file("o/r", "LICENSE")


async def test_search_repos_returns_items() -> None:
    def handler(request):
        return httpx.Response(200, json={"items": [{"id": 1}, {"id": 2}]})

    client = _client_with(handler)
    items = await client.search_repos("fastapi")
    assert len(items) == 2


async def test_circuit_breaker_open_raises() -> None:
    settings = get_settings()
    client = GitHubClient(
        settings=settings,
        clock=lambda: 1000.0,
    )
    # força o breaker aberto registrando falhas até o limiar
    for _ in range(settings.circuit_breaker_threshold):
        client._breaker.record_failure()
    with pytest.raises(GitHubUnavailableError):
        await client.get_file("o/r", "x")


# ---- Retry (http-request-mastery) ----
async def test_get_file_retries_transient_5xx_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"message": "unavailable"})
        content = base64.b64encode(b"MIT License").decode()
        return httpx.Response(200, json={"content": content, "encoding": "base64"})

    client = _client_with(handler)
    out = await client.get_file("o/r", "LICENSE", retry_kwargs=_retry_fast())
    assert "MIT" in out
    assert calls["n"] == 3  # 2 falhas + 1 sucesso


async def test_get_file_does_not_retry_client_error() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, json={"message": "bad request"})

    client = _client_with(handler)
    with pytest.raises(GitHubUnavailableError):
        await client.get_file("o/r", "x", retry_kwargs=_retry_fast())
    assert calls["n"] == 1  # erro 4xx não retenta


def _retry_fast() -> dict:
    return {"max_attempts": 3, "base_delay": 0.001, "max_delay": 0.002, "jitter_factor": 0}
