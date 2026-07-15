"""Circuit breaker para degradação graciosa de integrações externas.

Usado pelos clientes SRA/Firecrawl/GitHub (PRD F-003/F-008 e Spec §5):
- Após `failure_threshold` falhas seguidas, abre por `reset_after_seconds`.
- Chamadas enquanto aberto falham rápido (sem esperar timeout).
- Um sucesso reseta o contador.
- Relógio injetável para testes (dependency injection).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field


def _system_clock() -> float:
    return time.time()


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_after_seconds: float = 60.0
    clock: Callable[[], float] = field(default_factory=lambda: _system_clock)

    failures: int = 0
    open_until: float | None = None

    def __post_init__(self) -> None:
        # Clients passam clock=self._clock que pode ser None; normaliza para
        # o relógio de sistema afim de evitar TypeError em is_open()/record_*.
        if self.clock is None:
            self.clock = _system_clock

    def is_open(self) -> bool:
        now = self.clock()
        if self.open_until is not None and now < self.open_until:
            return True
        if self.open_until is not None:
            # janela de reset passou: fecha e reseta
            self.failures = 0
            self.open_until = None
        return False

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.open_until = self.clock() + self.reset_after_seconds

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = None
