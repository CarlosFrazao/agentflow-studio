"""Validação manual de SRA/Firecrawl/GitHub reais + simulação de falhas.

Roda FORA do FastAPI (sem auth, sem HTTP server). Objetivo: provar que
retry, circuit breaker e fallback funcionam com integrações reais.

Cenários:
  1. SRA MCP responde normalmente
  2. Firecrawl MCP responde normalmente
  3. Firecrawl REST responde normalmente
  4. Firecrawl MCP cai  -> fallback REST (real) funciona
  5. Firecrawl REST cai -> retry ativa (503 -> 200 via MockTransport)
  6. Ambos caem         -> FirecrawlUnavailable -> fallback GitHub (real)
  7. SRA cai            -> circuit breaker abre (bonus, alinhado ao objetivo)

Host morto p/ simular queda: http://127.0.0.1:9 (porta discard, conn refused).

Uso:
  cd backend && python scripts/validate_integrations.py
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.clients.github_client import GitHubClient, GitHubUnavailableError
from app.clients.mcp.firecrawl_client import FirecrawlClient, FirecrawlUnavailableError
from app.clients.mcp.sra_client import SRAClient, SRAUnavailableError
from app.core.config import Settings, get_settings

DEAD_HOST = "http://127.0.0.1:9"
TEST_URL = "https://fastapi.tiangolo.com/"
TEST_QUERY = "como criar api rest com fastapi"


def banner(n: int, title: str) -> None:
    print("\n" + "=" * 60)
    print(f"CENÁRIO {n}: {title}")
    print("=" * 60)


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def fail(msg: str) -> None:
    print(f"  [FALHOU] {msg}")


def warn(msg: str) -> None:
    print(f"  [AVISO] {msg}")


async def scenario_1_sra_ok(s: Settings) -> None:
    banner(1, "SRA MCP responde normalmente")
    client = SRAClient(settings=s)
    try:
        alive = await client.health()
        print(f"  health() -> {alive}")
        if alive:
            ok("MCP SSE do SRA respondeu (health ok)")
        else:
            warn("SRA não expõe tool 'health'; tentando research()")
        try:
            out = await client.research(TEST_QUERY)
            ok(f"research() retornou {len(out)} chars")
            print(f"    amostra: {out[:120]!r}")
        except SRAUnavailableError as exc:
            warn(f"research() indisponível (esperado se tool 'research' não existir): {exc}")
    except Exception as exc:  # noqa: BLE001
        fail(f"exceção inesperada: {type(exc).__name__}: {exc}")


async def scenario_2_firecrawl_mcp_ok(s: Settings) -> None:
    banner(2, "Firecrawl MCP responde normalmente")
    client = FirecrawlClient(settings=s)
    try:
        res = await client.scrape(TEST_URL)
        if client.supports_mcp:
            ok("Firecrawl via MCP SSE funcionou")
        else:
            warn("MCP indisponível — caiu sozinho pro REST (ver cenário 3)")
        print(f"    chaves: {list(res.keys())}; amostra: {str(res)[:120]!r}")
    except FirecrawlUnavailableError as exc:
        warn(f"Firecrawl indisponível (MCP e REST): {exc}")
    except Exception as exc:  # noqa: BLE001
        fail(f"exceção inesperada: {type(exc).__name__}: {exc}")


async def scenario_3_firecrawl_rest_ok(s: Settings) -> None:
    banner(3, "Firecrawl REST responde normalmente")
    client = FirecrawlClient(settings=s)
    client.supports_mcp = False  # força caminho REST
    try:
        res = await client.scrape(TEST_URL)
        ok("Firecrawl via REST /v2/scrape funcionou")
        print(f"    chaves: {list(res.keys())}; amostra: {str(res)[:120]!r}")
    except FirecrawlUnavailableError as exc:
        fail(f"REST real falhou: {exc}")
    except Exception as exc:  # noqa: BLE001
        fail(f"exceção inesperada: {type(exc).__name__}: {exc}")


async def scenario_4_firecrawl_mcp_down_fallback_rest(s: Settings) -> None:
    banner(4, "Firecrawl MCP cai -> fallback REST (real)")
    client = FirecrawlClient(settings=s)
    client._mcp_url = DEAD_HOST  # simula MCP indisponível
    try:
        res = await client.scrape(TEST_URL)
        if client.supports_mcp:
            warn("suports_mcp ainda True — fallback não foi acionado?")
        else:
            ok("MCP falhou e caiu para REST (real) com sucesso")
        print(f"    chaves: {list(res.keys())}; amostra: {str(res)[:120]!r}")
    except FirecrawlUnavailableError as exc:
        fail(f"esperava REST real funcionar, mas falhou: {exc}")
    except Exception as exc:  # noqa: BLE001
        fail(f"exceção inesperada: {type(exc).__name__}: {exc}")


async def scenario_5_firecrawl_rest_retry() -> None:
    banner(5, "Firecrawl REST cai -> retry ativa (503 -> 200)")
    # MockTransport determinístico: 503 nas 2 primeiras, 200 depois.
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(
            200, json={"data": {"markdown": "# ok depois de retry", "content": "retry funcionou"}}
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    s = Settings(firecrawl_api_key="x", firecrawl_call_timeout_s=5)
    client = FirecrawlClient(settings=s, http_client=http_client)
    client.supports_mcp = False
    try:
        res = await client.scrape(TEST_URL, retry_kwargs={
            "max_attempts": 3, "base_delay": 0.01, "max_delay": 0.02, "jitter_factor": 0
        })
        ok(f"retry recuperou após {calls['n']} tentativas; res={res}")
    except FirecrawlUnavailableError as exc:
        fail(f"retry deveria ter recuperado, mas falhou: {exc}")
    except Exception as exc:  # noqa: BLE001
        fail(f"exceção inesperada: {type(exc).__name__}: {exc}")
    finally:
        await http_client.aclose()


async def scenario_6_both_down_github_fallback(s: Settings) -> None:
    banner(6, "Ambos caem -> fallback GitHub (real)")
    fc = FirecrawlClient(settings=s)
    fc._mcp_url = DEAD_HOST
    fc._rest_url = DEAD_HOST  # ambos mortos
    firecrawl_failed = False
    try:
        await fc.scrape(TEST_URL)
        warn("Firecrawl retornou mesmo com ambos os hosts mortos (inesperado)")
    except FirecrawlUnavailableError as exc:
        firecrawl_failed = True
        ok(f"Firecrawl levantou FirecrawlUnavailableError como esperado: {exc}")

    if firecrawl_failed:
        gh = GitHubClient(settings=s)
        try:
            repos = await gh.search_repos("fastapi framework language:python", per_page=2)
            ok(f"fallback GitHub real retornou {len(repos)} repo(s)")
            if repos:
                print(f"    primeiro: {repos[0].get('full_name')}")
        except GitHubUnavailableError as exc:
            fail(f"GitHub real também falhou: {exc}")
        except Exception as exc:  # noqa: BLE001
            fail(f"exceção inesperada GitHub: {type(exc).__name__}: {exc}")


async def scenario_7_sra_down_breaker(s: Settings) -> None:
    banner(7, "SRA cai -> circuit breaker abre (bonus)")
    client = SRAClient(settings=s)
    client._mcp_url = DEAD_HOST
    opened = False
    for i in range(s.circuit_breaker_threshold + 1):
        try:
            await client.research(TEST_QUERY)
        except SRAUnavailableError:
            pass
    try:
        # próxima chamada deve ser barrada pelo breaker aberto
        await client.research(TEST_QUERY)
        warn("breaker não abriu após falhas repetidas")
    except SRAUnavailableError as exc:
        if "circuit_breaker_open" in str(exc):
            opened = True
            ok(f"circuit breaker abriu e barrou chamada: {exc}")
        else:
            fail(f"SRA falhou mas breaker não abriu: {exc}")
    except Exception as exc:  # noqa: BLE001
        fail(f"exceção inesperada: {type(exc).__name__}: {exc}")
    if not opened:
        fail("circuit breaker não entrou em estado aberto")


async def main() -> int:
    print("Carregando config real do .env (backend/.env)")
    try:
        s = get_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"Erro ao carregar Settings: {exc}", file=sys.stderr)
        return 1
    print(f"  SRA_MCP_URL       = {s.sra_mcp_url}")
    print(f"  FIRECRAWL_MCP_URL = {s.firecrawl_mcp_url}")
    print(f"  FIRECRAWL_REST_URL= {s.firecrawl_rest_url}")
    print(f"  GITHUB_API_URL    = {s.github_api_url}")
    print(f"  CIRCUIT threshold = {s.circuit_breaker_threshold}")

    await scenario_1_sra_ok(s)
    await scenario_2_firecrawl_mcp_ok(s)
    await scenario_3_firecrawl_rest_ok(s)
    await scenario_4_firecrawl_mcp_down_fallback_rest(s)
    await scenario_5_firecrawl_rest_retry()
    await scenario_6_both_down_github_fallback(s)
    await scenario_7_sra_down_breaker(s)

    print("\n" + "=" * 60)
    print("VALIDAÇÃO CONCLUÍDA")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
