"""Testes unitários do CircuitBreaker (TDD — lógica pura de degradação graciosa).

Cobertura alvo do PRD F-003/F-008: 80%.
"""

from collections.abc import Callable

import pytest

from app.clients.circuit_breaker import CircuitBreaker


class ManualClock:
    """Relógio injetável para controlar o avanço de tempo nos testes."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_breaker(clock: ManualClock) -> CircuitBreaker:
    return CircuitBreaker(
        failure_threshold=3,
        reset_after_seconds=60.0,
        clock=clock,  # type: ignore[arg-type]
    )


def test_starts_closed(clock: ManualClock) -> None:
    breaker = make_breaker(clock)
    assert breaker.is_open() is False
    assert breaker.failures == 0


def test_opens_after_threshold_failures(clock: ManualClock) -> None:
    breaker = make_breaker(clock)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open() is False  # ainda abaixo do limiar
    breaker.record_failure()
    assert breaker.is_open() is True  # 3ª falha abre


def test_records_success_resets_failures(clock: ManualClock) -> None:
    breaker = make_breaker(clock)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.failures == 0
    assert breaker.is_open() is False
    # nova sequência de falhas recomeça do zero
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open() is False


def test_recovers_after_reset_window(clock: ManualClock) -> None:
    breaker = make_breaker(clock)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open() is True
    # dentro da janela: ainda aberto
    clock.advance(59.0)
    assert breaker.is_open() is True
    # passou a janela: is_open() reseta e fecha
    clock.advance(2.0)
    assert breaker.is_open() is False
    assert breaker.failures == 0


def test_open_is_half_open_after_window_then_can_reopen(clock: ManualClock) -> None:
    breaker = make_breaker(clock)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open() is True
    clock.advance(61.0)
    assert breaker.is_open() is False  # janela passou -> fecha
    # se falhar de novo, reabre
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open() is True


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()
