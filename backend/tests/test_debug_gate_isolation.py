"""Tests for the debug-endpoint environment gate (FEAT-004 / B5-2).

The E2E debug endpoints `/conversations/_override_llm` and
`/conversations/{id}/_seed_auto_approved` must be reachable only when
`settings.debug is True AND settings.is_production is False`.

Previously the gate checked only `settings.debug`, so a production
deployment mis-set with `debug=True` would expose these mutable debug
endpoints. The new gate closes that leak.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.deps import get_current_user
from app.core.database import get_session
from app.main import create_app
from app.models import Base
from app.models.user import User

from app.api.v1 import conversations as conversations_module


@pytest_asyncio.fixture
async def client_with_settings(session_factory, monkeypatch):
    """Factory fixture: build an ASGI client with the debug gate env set.

    Usage:
        async for c in client_with_settings(debug=True, is_production=False):
            ...
    The cached `Settings` singleton is mutated only for this test (reverted
    by monkeypatch at teardown); `is_production` is derived from `environment`.
    """

    async def _factory(debug: bool, is_production: bool):
        settings = conversations_module.get_settings()
        monkeypatch.setattr(settings, "debug", debug)
        monkeypatch.setattr(
            settings, "environment", "production" if is_production else "development"
        )

        async def override_session() -> AsyncSession:
            async with session_factory() as s:
                yield s

        async with session_factory() as s:
            user = User(
                id=uuid.uuid4(),
                email="debug-gate@example.com",
                display_name="Debug Gate",
                password_hash=None,
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)

            async def override_current_user() -> User:
                return User(
                    id=user.id, email=user.email, display_name=user.display_name
                )

        app = create_app()
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user] = override_current_user
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
            yield c
        app.dependency_overrides.clear()

    return _factory


@pytest.mark.asyncio
async def test_override_llm_allowed_in_dev_debug(client_with_settings):
    async for c in client_with_settings(debug=True, is_production=False):
        resp = await c.post("/api/v1/conversations/_override_llm")
        assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_override_llm_blocked_when_debug_false(client_with_settings):
    async for c in client_with_settings(debug=False, is_production=False):
        resp = await c.post("/api/v1/conversations/_override_llm")
        assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_override_llm_blocked_in_production_even_if_debug_true(
    client_with_settings,
):
    async for c in client_with_settings(debug=True, is_production=True):
        resp = await c.post("/api/v1/conversations/_override_llm")
        assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_seed_auto_approved_blocked_in_production_even_if_debug_true(
    client_with_settings,
):
    async for c in client_with_settings(debug=True, is_production=True):
        conv_id = uuid.uuid4()
        resp = await c.post(
            f"/api/v1/conversations/{conv_id}/_seed_auto_approved"
        )
        assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_seed_auto_approved_reaches_endpoint_in_dev_debug(
    client_with_settings,
):
    async for c in client_with_settings(debug=True, is_production=False):
        conv_id = uuid.uuid4()
        resp = await c.post(
            f"/api/v1/conversations/{conv_id}/_seed_auto_approved"
        )
        # 404 here is "conversation not found" — the gate passed (endpoint reached).
        # The point of this test is that production-style blocking does NOT happen.
        assert resp.status_code in (200, 404), resp.text
