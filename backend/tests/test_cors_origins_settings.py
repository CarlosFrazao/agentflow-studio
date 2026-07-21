"""Tests for CORS origin configuration via settings (FEAT-010 / B1-3).

The audit (B1-3) required that CORS `allow_origins` be driven by `settings`
rather than hardcoded, so that production can pin a known set of origins while
dev keeps localhost. `app/main.py` already wires the middleware to
`settings.cors_origins`; these tests characterize that contract so a future
regression (hardcoding origins, or leaking dev localhost into prod) is caught.

CORS headers are only emitted when the request carries an `Origin` header;
with `allow_credentials=True` the middleware echoes back the exact origin
rather than `*`, and omits the header entirely for origins outside the allow
list.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
import app.main as main_module
from app.main import create_app
from app.core.database import get_session
from app.models import Base


@pytest_asyncio.fixture
async def session_factory():
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await eng.dispose()


@pytest_asyncio.fixture
async def cors_client(session_factory, monkeypatch):
    """Factory fixture: build an ASGI client with pinned `cors_origins`.

    `create_app()` reads the cached `Settings` singleton at call time, so we
    mutate `cors_origins` on that singleton before building the app. The change
    is reverted by monkeypatch at teardown. Session/auth overrides are omitted
    because `/api/v1/health` is unauthenticated.
    """

    async def _factory(origins):
        # Mutate the EXACT settings object `create_app()` reads
        # (`app.main.settings`, a module-level singleton captured at import).
        # Reading via `get_settings()` is unsafe on the full suite: another
        # test may have cleared the lru_cache, handing back a fresh instance
        # that `create_app()` would never consult.
        settings = main_module.settings
        monkeypatch.setattr(settings, "cors_origins", list(origins))

        async def override_session() -> AsyncSession:
            async with session_factory() as s:
                yield s

        app = create_app()
        app.dependency_overrides[get_session] = override_session
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
            yield c
        app.dependency_overrides.clear()

    return _factory


@pytest.mark.asyncio
async def test_allowed_origin_reflected_from_settings(cors_client) -> None:
    async for c in cors_client(["https://app.example.com"]):
        resp = await c.get(
            "/api/v1/health", headers={"Origin": "https://app.example.com"}
        )
        assert resp.status_code == 200
        assert (
            resp.headers.get("access-control-allow-origin")
            == "https://app.example.com"
        )


@pytest.mark.asyncio
async def test_disallowed_origin_rejected(cors_client) -> None:
    async for c in cors_client(["https://app.example.com"]):
        resp = await c.get(
            "/api/v1/health", headers={"Origin": "https://evil.example.com"}
        )
        assert resp.status_code == 200
        # No CORS header is echoed for origins outside the allow list.
        assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_preflight_echoes_origin_and_credentials(cors_client) -> None:
    async for c in cors_client(["https://app.example.com"]):
        resp = await c.options(
            "/api/v1/health",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert (
            resp.headers.get("access-control-allow-origin")
            == "https://app.example.com"
        )
        assert resp.headers.get("access-control-allow-credentials") == "true"
        assert "access-control-allow-methods" in resp.headers
        # Starlette echoes `Vary: Origin` so caches key on the request origin.
        assert resp.headers.get("vary") == "Origin"


@pytest.mark.asyncio
async def test_prod_no_dev_localhost_leak(cors_client) -> None:
    # Production pins only its own origin; dev localhost must NOT be implied.
    async for c in cors_client(["https://agentflow.prod"]):
        resp = await c.get(
            "/api/v1/health", headers={"Origin": "http://localhost:5173"}
        )
        assert "access-control-allow-origin" not in resp.headers
