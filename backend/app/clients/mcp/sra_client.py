"""Cliente do Smart Research Agent (SRA) via MCP SSE.

O SRA só expõe MCP (não REST para pesquisa). Se o MCP estiver indisponível,
o Research Agent deve degradar (card segue com aviso), não cair para REST.
"""

from urllib.parse import urlparse

from app.clients.circuit_breaker import CircuitBreaker
from app.clients.mcp.base import BaseMCPClient, MCPClientError
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("sra_client")


class SRAUnavailableError(Exception):
    """SRA indisponível — sinaliza degradação graciosa para o orquestrador."""


class SRAClient(BaseMCPClient):
    """Consome ferramentas de pesquisa do SRA via MCP SSE."""

    def __init__(
        self, settings: Settings | None = None, clock=None
    ) -> None:
        s = settings or get_settings()
        # O servidor MCP do SRA (self-hosted) rejeita o Host header automático
        # (421 Invalid Host header) quando acessado pela rede Docker pelo nome
        # do serviço; exige "localhost:<porta>" (o bind espera localhost).
        port = urlparse(s.sra_mcp_url).port
        extra_headers = {"Host": f"localhost:{port}"}
        super().__init__(
            mcp_url=s.sra_mcp_url,
            timeout_s=s.sra_call_timeout_s,
            settings=s,
            clock=clock,
            extra_headers=extra_headers,
        )
        self._breaker = CircuitBreaker(
            failure_threshold=s.circuit_breaker_threshold,
            reset_after_seconds=s.circuit_breaker_reset_s,
            clock=self._clock,  # type: ignore[arg-type]
        )
        # Ferramenta de pesquisa exposta pelo SRA (confirmada em /openapi.json).
        self._tool = "research_technology_v2"

    async def research(self, query: str, mode: str = "standard") -> str:
        if self._breaker.is_open():
            raise SRAUnavailableError("circuit_breaker_open")
        try:
            result = await self.call_tool(
                self._tool, {"query": query, "mode": mode, "include_confidence": True}
            )
            self._breaker.record_success()
            return result.get("text", "")
        except MCPClientError as exc:
            self._breaker.record_failure()
            raise SRAUnavailableError(str(exc)) from exc

    async def health(self) -> bool:
        # SRA não expõe tool "health" no MCP; usa probe de handshake SSE.
        return await self.health_probe()
