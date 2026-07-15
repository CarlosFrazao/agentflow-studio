"""Testes TDD do Event Bus (Item 3 da Fase 1).

Barramento pub/sub desacoplado via asyncio.Queue:
- Um publisher publica eventos tipados.
- Um subscriber consome os eventos na ordem.
- Subscribers independentes recebem a mesma mensagem.
"""

import asyncio
import pytest

from app.services.event_bus import EventBus, Event

pytestmark = pytest.mark.asyncio


async def test_publish_and_subscribe_ordered() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    bus.publish(Event(type="card.created", payload={"id": 1}))
    bus.publish(Event(type="card.moved", payload={"id": 1, "to": "done"}))
    # consome na ordem
    e1 = await asyncio.wait_for(sub.get(), timeout=1.0)
    e2 = await asyncio.wait_for(sub.get(), timeout=1.0)
    assert e1.type == "card.created"
    assert e2.type == "card.moved"
    assert e2.payload["to"] == "done"


async def test_multiple_subscribers_receive_same_event() -> None:
    bus = EventBus()
    a = bus.subscribe()
    b = bus.subscribe()
    bus.publish(Event(type="agent.run", payload={"agent": "dev"}))
    ea = await asyncio.wait_for(a.get(), timeout=1.0)
    eb = await asyncio.wait_for(b.get(), timeout=1.0)
    assert ea.type == eb.type == "agent.run"
