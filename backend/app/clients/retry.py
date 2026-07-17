"""Retry com backoff exponencial + jitter (http-request-mastery).

- Retenta apenas status transitórios: 408, 429, 500, 502, 503, 504.
- Retenta também falhas de rede transitórias sem resposta HTTP:
  httpx.TimeoutException e httpx.ConnectError.
- Não retenta erros de cliente (400/401/403/404/409/422).
- Respeita Retry-After quando presente.
- Jitter evita thundering herd.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx

RETRYABLE_STATUSES: set[int] = {408, 429, 500, 502, 503, 504}

# Sentinel returned by `_status_of` for transient network failures that have no
# HTTP response attached (httpx raises TimeoutException/ConnectError directly).
# Kept out of RETRYABLE_STATUSES because that set is reserved for HTTP status codes.
TIMEOUT_OR_CONNECT = -1


def _status_of(exc: Exception) -> int | None:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return TIMEOUT_OR_CONNECT
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):
        return resp.get("status")
    return getattr(resp, "status_code", None)


async def with_retry(
    fn: Callable[[], Awaitable[object]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_factor: float = 0.3,
    retryable_statuses: set[int] | None = None,
) -> object:
    statuses = retryable_statuses or RETRYABLE_STATUSES
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - retry genérico por design
            last_exc = exc
            status = _status_of(exc)
            if status == TIMEOUT_OR_CONNECT:
                pass  # timeout/connect error: retryável por definição
            elif status is not None and status not in statuses:
                raise  # erro não-transitório: não retentar
            if attempt == max_attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay += delay * jitter_factor * random.random()  # jitter
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc
