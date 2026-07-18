"""Path traversal hardening on the SPA catch-all fallback (FEAT-005).

The static build is served from settings.static_dir. A crafted path such as
`/../../../backend/.env` must never escape that directory and serve secrets.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app, settings as app_settings

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "spa_root"


@pytest.fixture
async def spa_client():
    # create_app() reads the module-level `settings` instance captured at import
    # time in app.main, so override that instance (not just get_settings()).
    app_settings.static_dir = FIXTURE_ROOT
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def test_spa_serves_index(spa_client: AsyncClient) -> None:
    resp = await spa_client.get("/")
    assert resp.status_code == 200
    assert "<div id=\"root\">" in resp.text


async def test_spa_serves_asset(spa_client: AsyncClient) -> None:
    resp = await spa_client.get("/assets/app.js")
    assert resp.status_code == 200
    assert "agentflow spa asset" in resp.text


async def test_spa_traversal_blocked(spa_client: AsyncClient) -> None:
    # Attempt to escape static_dir and read the backend .env (outside the build).
    backend_env = (
        Path(__file__).resolve().parent.parent / "app" / "core" / "config.py"
    )
    assert backend_env.exists()
    resp = await spa_client.get("/../../../app/core/config.py")
    # Must NOT serve the out-of-tree file: either 404 (handled) or the SPA
    # index fallback, but never the requested sensitive file's contents.
    assert "class Settings" not in resp.text
    assert resp.status_code in (200, 404)
