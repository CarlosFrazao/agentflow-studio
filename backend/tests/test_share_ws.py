"""Testes do WebSocket de compartilhamento (Item D — tempo real).

Usa o TestClient do Starlette (síncrono) para abrir a conexão WS e
verificar que eventos publicados no EventBus chegam ao cliente.
"""

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.services.event_bus import Event, event_bus


def test_share_ws_receives_published_event() -> None:
    app = create_app()
    # Desativa override de auth (WS é público) e usa sessão real em memória
    # não é necessário: o endpoint WS não toca DB.
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/share/proj-123/ws") as ws:
            # sinal de connected
            first = ws.receive_json()
            assert first["type"] == "connected"
            # publica um evento que o WS deve transmitir
            event_bus.publish(
                Event(
                    type="card.updated",
                    payload={"card_id": "c1", "project_id": "proj-123", "column": "done"},
                )
            )
            msg = ws.receive_json()
            assert msg["type"] == "card.updated"
            assert msg["payload"]["column"] == "done"


def test_share_ws_filters_other_projects() -> None:
    app = create_app()
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/share/proj-A/ws") as ws:
            ws.receive_json()  # connected
            # evento de OUTRO projeto deve ser ignorado
            event_bus.publish(
                Event(type="card.updated", payload={"project_id": "proj-B", "column": "done"})
            )
            # evento do projeto A deve chegar
            event_bus.publish(
                Event(type="card.created", payload={"project_id": "proj-A", "column": "backlog"})
            )
            msg = ws.receive_json()
            assert msg["payload"]["project_id"] == "proj-A"
