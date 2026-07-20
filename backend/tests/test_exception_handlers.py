"""Tests for the exception handlers (FEAT-002 / B1-1).

Guarantees that error envelopes propagate a real request_id:
- with header X-Request-ID: the header value reappears in the envelope;
- without header: a valid, non-empty UUID is generated (uuid4 fallback).

The 401 (AppError) path is exercised against the real app + auth guard via
`anon_client`. The 404 (NotFoundError) and 500 (Exception) paths need a route
that actually raises before the SPA catch-all swallows it, so a minimal app
registers only the handlers and dedicated test routes.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.exceptions import NotFoundError
from app.main import _register_exception_handlers


def _build_handler_app() -> FastAPI:
    """App with only the exception handlers + routes that raise."""
    app = FastAPI()
    _register_exception_handlers(app)

    @app.get("/missing")
    async def _missing() -> dict:
        raise NotFoundError("Resource", "missing-id")

    @app.get("/crash")
    async def _crash() -> dict:
        raise RuntimeError("boom")

    return app


@pytest.mark.asyncio
async def test_app_error_401_propagates_request_id_header(
    anon_client: AsyncClient,
) -> None:
    """AppError (401 from the auth guard) propagates the X-Request-ID header."""
    resp = await anon_client.get(
        "/api/v1/projects",
        headers={"X-Request-ID": "req-401"},
    )
    assert resp.status_code == 401
    assert resp.json()["meta"]["request_id"] == "req-401"


def test_404_not_found_propagates_request_id_header() -> None:
    """Criterion 4.2.2: 404 with X-Request-ID: abc -> envelope carries abc."""
    app = _build_handler_app()
    resp = TestClient(app).get(
        "/missing", headers={"X-Request-ID": "abc-123"}
    )
    assert resp.status_code == 404
    assert resp.json()["meta"]["request_id"] == "abc-123"


def test_404_not_found_generates_uuid_without_header() -> None:
    """Criterion 4.2.2: without header, request_id is a valid non-empty UUID."""
    app = _build_handler_app()
    resp = TestClient(app).get("/missing")
    assert resp.status_code == 404
    rid = resp.json()["meta"]["request_id"]
    assert rid  # non-empty
    assert uuid.UUID(rid)  # valid UUID format


def test_unhandled_exception_propagates_request_id() -> None:
    """Unhandled Exception (500) handler propagates the X-Request-ID header.

    Uses TestClient with raise_server_exceptions=False so the 500 response
    (produced by our handler after the ServerErrorMiddleware) reaches the
    caller instead of being re-raised by the transport.
    """
    app = _build_handler_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/crash", headers={"X-Request-ID": "req-500"})
    assert resp.status_code == 500
    assert resp.json()["meta"]["request_id"] == "req-500"
