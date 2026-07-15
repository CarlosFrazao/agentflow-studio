"""Testes adicionais do EventBus para elevar cobertura (Item 5)."""

import asyncio

import pytest

from app.services.event_bus import Event, EventBus

pytestmark = pytest.mark.asyncio


async def test_unsubscribe_stops_receiving() -> None:
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.publish(Event(type="x"))
    # fila vazia não deve bloquear indefinidamente
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.2)


async def test_stream_yields_events() -> None:
    bus = EventBus()
    collected = []

    async def consume():
        async for ev in bus.stream():
            collected.append(ev.type)
            if ev.type == "stop":
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    bus.publish(Event(type="a"))
    bus.publish(Event(type="stop"))
    await asyncio.wait_for(task, timeout=1.0)
    assert collected == ["a", "stop"]
