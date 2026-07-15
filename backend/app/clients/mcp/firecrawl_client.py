"""Cliente do Firecrawl (self-hosted) via MCP SSE com fallback REST.

URLs validadas pelo usuário (2026-07-11):
- MCP SSE:  http://firecrawl-api-new:3002/mcp/sse
- REST:     http://firecrawl-api-new:3002   (fallback se SSE não exposto)

Prioridade do Code Research Agent (Spec §2.5): GitHub API para código dentro do
github.com; Firecrawl reservado para conteúdo fora do GitHub (docs/blogs).
"""

from collections.abc import Callable

import httpx

from app.clients.circuit_breaker import CircuitBreaker
from app.clients.mcp.base import BaseMCPClient, MCPClientError
from app.clients.retry import with_retry
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("firecrawl_client")


class FirecrawlClient(BaseMCPClient):
    """Firecrawl com transporte MCP, recaindo para REST quando necessário."""

    def __init__(
        self,
        settings: Settings | None = None,
        clock: Callable[[], float] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        s = settings or get_settings()
        super().__init__(
            mcp_url=s.firecrawl_mcp_url,
            timeout_s=s.firecrawl_call_timeout_s,
            settings=s,
            clock=clock,
        )
        self._rest_url = s.firecrawl_rest_url.rstrip("/")
        self._api_key = s.firecrawl_api_key
        self._http_client = http_client
        self._breaker = CircuitBreaker(
            failure_threshold=s.circuit_breaker_threshold,
            reset_after_seconds=s.circuit_breaker_reset_s,
            clock=clock,  # type: ignore[arg-type]
        )
        self.supports_mcp = True

    async def scrape(self, url: str, *, retry_kwargs: dict | None = None) -> dict:
        """Coleta uma página em markdown limpo (MCP, fallback REST /v2/scrape)."""
        if self._breaker.is_open():
            raise FirecrawlUnavailableError("circuit_breaker_open")
        if self.supports_mcp:
            try:
                result = await self.call_tool("scrape", {"url": url})
                self._breaker.record_success()
                return result
            except MCPClientError as exc:
                logger.warning("firecrawl_mcp_unavailable_falling_back", error=str(exc))
                self.supports_mcp = False  # MCP ausente -> usa REST daqui p/ frente
        return await self._scrape_rest(url, retry_kwargs=retry_kwargs)

    async def _scrape_rest(self, url: str, *, retry_kwargs: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async def _do() -> dict:
            if self._http_client is not None:
                resp = await self._http_client.post(
                    f"{self._rest_url}/v2/scrape", json={"url": url}, headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.post(
                        f"{self._rest_url}/v2/scrape", json={"url": url}, headers=headers
                    )
            resp.raise_for_status()
            return resp.json()

        try:
            # retry de falhas transitórias (429/5xx/timeout); MCP é coberto
            # só pelo circuit breaker (não se aplica HTTP retry ao transporte SSE).
            data = await with_retry(_do, **(retry_kwargs or {}))
            self._breaker.record_success()
            return data
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            self._breaker.record_failure()
            raise FirecrawlUnavailableError(str(exc)) from exc


class FirecrawlUnavailableError(Exception):
    """Firecrawl indisponível — Code Research Agent degrada para só GitHub API."""
