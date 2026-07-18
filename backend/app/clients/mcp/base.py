"""Cliente MCP base (SSE remoto).

Conecta-se a um servidor MCP que já está no ar (SRA/Firecrawl no Docker Desktop)
via transporte SSE. Não spawna subprocesso (não é STDIO local).

Estratégia de fallback: se a conexão SSE não estiver disponível, a flag
`supports_mcp` fica False e o cliente concreto decide usar REST (Firecrawl)
ou degradar (SRA).
"""

from collections.abc import Callable

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("mcp_base")


class MCPClientError(Exception):
    """Erro de comunicação com servidor MCP."""


class BaseMCPClient:
    """Wrapper mínimo de sessão MCP sobre SSE."""

    def __init__(
        self,
        mcp_url: str,
        *,
        timeout_s: float,
        settings: Settings | None = None,
        clock: Callable[[], float] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._mcp_url = mcp_url
        self._timeout_s = timeout_s
        self._clock = clock
        # Headers extras (ex: Host exigido pelo servidor MCP do SRA atrás de proxy).
        self._extra_headers = extra_headers
        self.supports_mcp = True  # ajustado pelo cliente concreto em setup()

    async def health_probe(self) -> bool:
        """Testa conectividade MCP (handshake SSE) sem chamar ferramenta."""
        try:
            async with sse_client(self._mcp_url, headers=self._extra_headers) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.close()
            return True
        except Exception as exc:  # noqa: BLE001 - qualquer falha = indisponível
            logger.warning("mcp_health_probe_failed", url=self._mcp_url, error=str(exc))
            return False

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Chama uma ferramenta MCP e retorna o primeiro conteúdo estruturado."""
        try:
            async with sse_client(self._mcp_url, headers=self._extra_headers) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
        except Exception as exc:  # conexão recusada, timeout, protocolo
            logger.warning(
                "mcp_call_failed", url=self._mcp_url, tool=name, error=str(exc)
            )
            raise MCPClientError(f"MCP call '{name}' falhou: {exc}") from exc

        if not result.content:
            return {}
        first = result.content[0]
        if hasattr(first, "text"):
            return {"text": first.text}
        return {"data": first.model_dump()}
