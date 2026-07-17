"""Event Bus desacoplado (pub/sub) para comunicação entre agentes (Item 3).

Cada subscriber recebe sua própria asyncio.Queue; o publisher faz fan-out
copiando o evento para todas as filas. Isso mantém os agentes fracamente
acoplados: um agente publica um Event e não sabe quem o consome.
"""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger("event_bus")


@dataclass
class Event:
    """Mensagem tipada trocada pelo barramento."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Barramento pub/sub em memória baseado em asyncio.Queue."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []

    def subscribe(self) -> asyncio.Queue[Event]:
        """Registra um novo assinante e devolve sua fila de eventos."""
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(queue)
        logger.debug("event_bus_subscribe", total=len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Remove um assinante previamente registrado."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, event: Event) -> None:
        """Faz fan-out do evento para todos os assinantes ativos.

        Usa ``call_soon_threadsafe`` com o loop dono de cada ``asyncio.Queue``
        para garantir que o ``await queue.get()`` acorde mesmo quando o
        publicador roda em um event loop diferente do assinante (cenário
        comum em testes com Starlette TestClient, cujo WebSocket executa em
        loop/thread próprios). O fallback ``put_nowait`` cobre o caso em que
        a queue não esteja bound a nenhum loop (loop=None).
        """
        for q in list(self._subscribers):
            loop = getattr(q, "_loop", None)
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(q.put_nowait, event)
            else:
                q.put_nowait(event)
        logger.debug("event_bus_publish", type=event.type, fans=len(self._subscribers))

    async def stream(self) -> AsyncGenerator[Event, None]:
        """Helper assíncrono para consumir eventos de um subscriber recém-criado."""
        queue = self.subscribe()
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(queue)


# Singleton do barramento — usado pelo WebSocket de compartilhamento e por
# quem quiser publicar/consumir eventos de cards em tempo real.
event_bus = EventBus()
