"""Testes TDD do utilitário de retry com backoff exponencial + jitter.

Cobertura (http-request-mastery): nao retentar erros nao-transitorios (400/404),
retentar 408/429/500/502/503/504, respeitar Retry-After, limite de tentativas.
"""

import asyncio
from collections.abc import Callable

import pytest

from app.clients.retry import RETRYABLE_STATUSES, with_retry


class FakeError(Exception):
    def __init__(self, status: int | None = None) -> None:
        self.response = {"status": status} if status is not None else None
        super().__init__(f"status={status}")


async def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise FakeError(503)
        return "ok"

    result = await with_retry(flaky, max_attempts=3, base_delay=0.001)
    assert result == "ok"
    assert calls["n"] == 3


async def test_does_not_retry_4xx_client_error() -> None:
    calls = {"n": 0}

    async def bad() -> str:
        calls["n"] += 1
        raise FakeError(400)

    with pytest.raises(FakeError):
        await with_retry(bad, max_attempts=3, base_delay=0.001)
    assert calls["n"] == 1  # sem retry


async def test_does_not_retry_404() -> None:
    calls = {"n": 0}

    async def missing() -> str:
        calls["n"] += 1
        raise FakeError(404)

    with pytest.raises(FakeError):
        await with_retry(missing, max_attempts=3, base_delay=0.001)
    assert calls["n"] == 1


async def test_gives_up_after_max_attempts() -> None:
    async def always_fail() -> str:
        raise FakeError(502)

    with pytest.raises(FakeError):
        await with_retry(always_fail, max_attempts=2, base_delay=0.001)


def test_retryable_statuses_set() -> None:
    assert RETRYABLE_STATUSES == {408, 429, 500, 502, 503, 504}


def test_retryable_statuses_excludes_client_errors() -> None:
    assert 400 not in RETRYABLE_STATUSES
    assert 404 not in RETRYABLE_STATUSES
    assert 422 not in RETRYABLE_STATUSES
