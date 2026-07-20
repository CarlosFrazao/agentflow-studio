"""Testes do WebSocket de compartilhamento (Item D — tempo real).

OWASP API1 (BOLA): o WebSocket agora exige JWT (query param `token`) e
valida que o project_id pertence ao usuário antes de aceitar a conexão.

Usa TestClient (sync) para HTTP e WS no mesmo event loop, e um arquivo
SQLite temporário (não :memory:) porque :memory:+aiosqlite é loop-bound.
O engine global é redirecionado para o tempfile na fixture ws_app.
"""

import os
import tempfile
import asyncio

import pytest
from starlette.testclient import TestClient
from uuid import uuid4

from app.main import create_app
from app.models import Base
from app.services.event_bus import Event, event_bus


@pytest.fixture(scope="function")
def ws_app():
    """App com engine apontando para SQLite temp + schema.

    Cria um novo event loop para o TestClient, evitando conflito com o loop
    do conftest (que usa :memory: para async tests). O tempfile é usado
    porque :memory: é loop-bound.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    eng = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    from app import core

    db_core = core.database
    orig_engine = db_core.engine
    orig_factory = db_core.AsyncSessionFactory
    db_core.engine = eng
    db_core.AsyncSessionFactory = async_sessionmaker(
        eng, expire_on_commit=False, class_=AsyncSession
    )

    # Cria um novo event loop (não reutiliza o do conftest, que pode estar fechado)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _schema():
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_schema())

    # O schema já veio do create_all acima; desativa o init_db() do lifespan
    # (que rodaria `alembic upgrade head` e reaplicaria a migration 0004,
    # gerando "duplicate column name: user_id"). Mantém o app íntegro para o WS.
    import app.core.database as _db
    import app.main as _main

    _orig_init_db_db = _db.init_db
    _orig_init_db_main = _main.init_db

    async def _noop_init_db() -> None:
        return None

    _db.init_db = _noop_init_db  # type: ignore[assignment]
    _main.init_db = _noop_init_db  # type: ignore[assignment]

    app = create_app()
    app.state._test_db_path = path
    app.state._test_db_restore = (db_core, orig_engine, orig_factory)
    app.state._test_loop = loop
    yield app
    # Cleanup
    db_core.engine = orig_engine
    db_core.AsyncSessionFactory = orig_factory
    _db.init_db = _orig_init_db_db  # type: ignore[assignment]
    _main.init_db = _orig_init_db_main  # type: ignore[assignment]
    try:
        os.unlink(path)
    except OSError:
        pass
    try:
        loop.close()
    except Exception:
        pass


def _register_owner(client: TestClient) -> tuple[str, str]:
    """Registra usuário + cria projeto via HTTP. Retorna (token, project_id)."""
    email = f"ws-owner-{uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "T3st!Pass9", "display_name": "Owner"},
    )
    assert r.status_code == 201, r.text
    tok = r.json()["data"]["access_token"]
    p = client.post(
        "/api/v1/projects",
        json={"name": "P"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert p.status_code == 201, p.text
    return tok, p.json()["data"]["id"]


def test_share_ws_requires_token(ws_app: TestClient) -> None:
    """Sem token -> WebSocket deve fechar (authz falhou)."""
    with TestClient(ws_app) as client:
        tok, pid = _register_owner(client)
        try:
            with client.websocket_connect(f"/api/v1/share/{pid}/ws") as ws:
                ws.receive_json()
            raise AssertionError("esperava WebSocketDisconnect sem token")
        except Exception as exc:
            assert "WebSocketDisconnect" in type(exc).__name__


def test_share_ws_owner_receives_event(ws_app: TestClient) -> None:
    """Usuário dono do projeto recebe evento do EventBus."""
    with TestClient(ws_app) as client:
        tok, pid = _register_owner(client)
        with client.websocket_connect(f"/api/v1/share/{pid}/ws?token={tok}") as ws:
            first = ws.receive_json()
            assert first["type"] == "connected"
            event_bus.publish(
                Event(
                    type="card.updated",
                    payload={"card_id": "c1", "project_id": pid, "column": "done"},
                )
            )
            msg = ws.receive_json()
            assert msg["type"] == "card.updated"
            assert msg["payload"]["column"] == "done"


def test_share_ws_rejects_other_user(ws_app: TestClient) -> None:
    """Outro usuário (não dono) tem conexão fechada."""
    with TestClient(ws_app) as client:
        tok_a, pid = _register_owner(client)
        email_b = f"ws-other-{uuid4().hex[:8]}@example.com"
        r2 = client.post(
            "/api/v1/auth/register",
            json={"email": email_b, "password": "T3st!Pass9", "display_name": "X"},
        )
        tok_b = r2.json()["data"]["access_token"]
        try:
            with client.websocket_connect(
                f"/api/v1/share/{pid}/ws?token={tok_b}"
            ) as ws:
                ws.receive_json()
            raise AssertionError("esperava WebSocketDisconnect para outro usuario")
        except Exception as exc:
            assert "WebSocketDisconnect" in type(exc).__name__


def test_share_ws_filters_other_projects(ws_app: TestClient) -> None:
    """Mesmo dono, outro project_id -> evento filtrado (defesa em profundidade)."""
    with TestClient(ws_app) as client:
        tok, pid = _register_owner(client)
        other_pid = uuid4().hex
        with client.websocket_connect(f"/api/v1/share/{pid}/ws?token={tok}") as ws:
            ws.receive_json()
            event_bus.publish(
                Event(type="card.created", payload={"project_id": other_pid, "column": "backlog"})
            )
            event_bus.publish(
                Event(type="card.created", payload={"project_id": pid, "column": "backlog"})
            )
            msg = ws.receive_json()
            assert msg["payload"]["project_id"] == pid