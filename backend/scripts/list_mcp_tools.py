"""Lista as ferramentas expostas por um servidor MCP SSE (SRA ou Firecrawl).

Uso:
  cd backend && PYTHONPATH=. python scripts/list_mcp_tools.py <url>
Ex:
  PYTHONPATH=. python scripts/list_mcp_tools.py http://sra-app:3458/mcp/sse
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.core.config import get_settings


async def list_tools(url: str) -> int:
    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
    except Exception as exc:  # noqa: BLE001
        print(f"ERRO ao conectar em {url}: {type(exc).__name__}: {exc}")
        return 1
    print(f"\nTools em {url} ({len(tools.tools)}):")
    for t in tools.tools:
        print(f"  - {t.name}: {t.description or '(sem descrição)'}[:80]")
    return 0


if __name__ == "__main__":
    s = get_settings()
    url = sys.argv[1] if len(sys.argv) > 1 else s.sra_mcp_url
    sys.exit(asyncio.run(list_tools(url)))
