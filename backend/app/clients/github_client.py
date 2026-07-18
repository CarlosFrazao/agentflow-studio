"""Cliente da GitHub API (REST direto).

Sem MCP: a GitHub API é pública e REST é mais rápido/barato que o Firecrawl
para arquivos de código dentro do github.com (Spec §2.5, PRD F-008).

Resilience (http-request-mastery): circuit breaker para degradação graciosa +
retry com backoff exponencial/jitter para falhas transitórias (408/429/5xx).
"""

from collections.abc import Callable

import httpx

from app.clients.circuit_breaker import CircuitBreaker
from app.clients.retry import with_retry
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("github_client")


class GitHubUnavailableError(Exception):
    """GitHub indisponível ou rate-limited."""


class GitHubClient:
    def __init__(
        self,
        settings: Settings | None = None,
        clock: Callable[[], float] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        s = settings or get_settings()
        self._base = s.github_api_url.rstrip("/")
        self._token = s.github_token
        self._timeout_s = s.github_call_timeout_s
        self._http_client = http_client
        self._breaker = CircuitBreaker(
            failure_threshold=s.circuit_breaker_threshold,
            reset_after_seconds=s.circuit_breaker_reset_s,
            clock=clock,  # type: ignore[arg-type]
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(
        self, method: str, url: str, *, retry_kwargs: dict | None = None, **kwargs
    ) -> httpx.Response:
        """Executa request HTTP com retry de falhas transitórias (429/5xx/timeout).

        Circuit breaker cobre falhas persistentes; aqui só suavizamos picos
        transitórios antes de desistir (http-request-mastery).
        """

        async def _do() -> httpx.Response:
            if self._http_client is not None:
                resp = await self._http_client.request(method, url, **kwargs)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp

        return await with_retry(_do, **(retry_kwargs or {}))

    async def get_file(
        self,
        repo: str,
        path: str,
        ref: str = "main",
        *,
        retry_kwargs: dict | None = None,
    ) -> str:
        """Lê arquivo bruto (ex: LICENSE, README.md) via Contents API."""
        if self._breaker.is_open():
            raise GitHubUnavailableError("circuit_breaker_open")
        url = f"{self._base}/repos/{repo}/contents/{path}?ref={ref}"
        try:
            import base64

            resp = await self._request(
                "GET", url, retry_kwargs=retry_kwargs, headers=self._headers()
            )
            data = resp.json()
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except (httpx.HTTPError, httpx.TimeoutException, KeyError, ValueError) as exc:
            self._breaker.record_failure()
            raise GitHubUnavailableError(str(exc)) from exc
        else:
            self._breaker.record_success()

    async def search_repos(
        self, query: str, per_page: int = 15, *, retry_kwargs: dict | None = None
    ) -> list[dict]:
        if self._breaker.is_open():
            raise GitHubUnavailableError("circuit_breaker_open")
        url = f"{self._base}/search/repositories"
        try:
            resp = await self._request(
                "GET",
                url,
                retry_kwargs=retry_kwargs,
                headers=self._headers(),
                params={"q": query, "per_page": per_page},
            )
            return resp.json().get("items", [])
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            self._breaker.record_failure()
            raise GitHubUnavailableError(str(exc)) from exc
        else:
            self._breaker.record_success()
