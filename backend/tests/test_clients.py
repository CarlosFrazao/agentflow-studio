"""Testes de instanciação e degradação dos clientes externos.

Valida: timeout/URLs do config, e que os clients herdam o circuit breaker.
Chamadas de rede reais são evitadas (TDD: testa comportamento, não I/O).
"""

from collections.abc import Callable

import pytest

from app.clients.circuit_breaker import CircuitBreaker
from app.clients.github_client import GitHubClient, GitHubUnavailableError
from app.clients.mcp.firecrawl_client import FirecrawlClient, FirecrawlUnavailableError
from app.clients.mcp.sra_client import SRAClient, SRAUnavailableError
from app.core.config import Settings


@pytest.fixture
def manual_clock():
    class Clock:
        def __init__(self) -> None:
            self.now = 1000.0

        def __call__(self) -> float:
            return self.now

        def advance(self, s: float) -> None:
            self.now += s

    return Clock()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        sra_mcp_url="http://sra-app:3458/mcp/sse",
        sra_call_timeout_s=90.0,
        firecrawl_mcp_url="http://firecrawl-api-new:3002/mcp/sse",
        firecrawl_rest_url="http://firecrawl-api-new:3002",
        github_api_url="https://api.github.com",
    )


def test_sra_client_uses_validated_urls(settings: Settings) -> None:
    client = SRAClient(settings=settings)
    assert client._mcp_url == "http://sra-app:3458/mcp/sse"
    assert client._timeout_s == 90.0


def test_firecrawl_client_has_mcp_and_rest_urls(settings: Settings) -> None:
    client = FirecrawlClient(settings=settings)
    assert client._mcp_url == "http://firecrawl-api-new:3002/mcp/sse"
    assert client._rest_url == "http://firecrawl-api-new:3002"
    assert client.supports_mcp is True


def test_github_client_has_public_api_url(settings: Settings) -> None:
    client = GitHubClient(settings=settings)
    assert client._base == "https://api.github.com"


async def test_sra_raises_unavailable_when_breaker_open(
    settings: Settings, manual_clock: Callable[[], float]
) -> None:
    client = SRAClient(settings=settings, clock=manual_clock)
    client._breaker.open_until = manual_clock.now + 60.0  # força aberto
    with pytest.raises(SRAUnavailableError):
        await client.research("ideia de app")


async def test_firecrawl_raises_unavailable_when_breaker_open(
    settings: Settings, manual_clock: Callable[[], float]
) -> None:
    client = FirecrawlClient(settings=settings, clock=manual_clock)
    client._breaker.open_until = manual_clock.now + 60.0
    with pytest.raises(FirecrawlUnavailableError):
        await client.scrape("https://docs.exemplo.dev")


async def test_github_raises_unavailable_when_breaker_open(
    settings: Settings, manual_clock: Callable[[], float]
) -> None:
    client = GitHubClient(settings=settings, clock=manual_clock)
    client._breaker.open_until = manual_clock.now + 60.0
    with pytest.raises(GitHubUnavailableError):
        await client.get_file("owner/repo", "LICENSE")
