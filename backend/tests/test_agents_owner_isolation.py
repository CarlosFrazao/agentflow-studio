"""Owner-isolation tests for the declarative agents API (FEAT-003 / B5-1).

Verifies that a user cannot update/delete an agent owned by another user
(IDOR prevention). Shared agents (user_id=NULL) remain readable but are
created with an owner in this flow, so cross-user mutation must 404.
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
from app.core.security import create_access_token
from app.main import create_app
from app.models import Base
from app.models.user import User
from app.schemas.agent import AgentCreate
from app.services import agent_definitions as svc

pytestmark = pytest.mark.asyncio

API = "/api/v1/agents"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_user(session_factory, email: str) -> User:
    async with session_factory() as s:
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=email,
            password_hash=None,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return User(id=user.id, email=user.email, display_name=user.display_name)


def _client_for(session_factory, user: User):
    """Build an AsyncClient whose auth guard resolves to `user`."""
    app = create_app()

    async def override_session() -> AsyncSession:
        async with session_factory() as s:
            yield s

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_current_user
    transport = ASGITransport(app=app)
    return app, AsyncClient(transport=transport, base_url="http://testserver")


@pytest_asyncio.fixture
async def users(session_factory):
    alice = await _seed_user(session_factory, "alice@example.com")
    bob = await _seed_user(session_factory, "bob@example.com")
    return alice, bob


async def _create_agent(session_factory, owner: User, name: str):
    async with session_factory() as s:
        await svc.create_agent(
            AgentCreate(
                name=name,
                model="gpt-4o",
                system_prompt="x",
                allowed_tools=[],
                max_tokens_budget=1.0,
            ),
            s,
            user_id=owner.id,
        )


async def test_owner_can_delete_own_agent(session_factory, users, tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    alice, _ = users
    await _create_agent(session_factory, alice, "alice-agent")

    _, client = _client_for(session_factory, alice)
    async with client:
        resp = await client.delete(f"{API}/alice-agent")
        assert resp.status_code == 204
        follow = await client.get(f"{API}/alice-agent")
        assert follow.status_code == 404


async def test_other_user_cannot_delete_agent_returns_404(
    session_factory, users, tmp_path, monkeypatch
):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    alice, bob = users
    await _create_agent(session_factory, alice, "alice-private")

    # Bob (different user) tries to delete Alice's agent.
    _, bob_client = _client_for(session_factory, bob)
    async with bob_client:
        resp = await bob_client.delete(f"{API}/alice-private")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    # Alice's agent must still exist (not deleted by Bob).
    _, alice_client = _client_for(session_factory, alice)
    async with alice_client:
        follow = await alice_client.get(f"{API}/alice-private")
        assert follow.status_code == 200


async def test_other_user_cannot_update_agent_returns_404(
    session_factory, users, tmp_path, monkeypatch
):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    alice, bob = users
    await _create_agent(session_factory, alice, "alice-upd")

    _, bob_client = _client_for(session_factory, bob)
    async with bob_client:
        resp = await bob_client.put(
            f"{API}/alice-upd", json={"system_prompt": "hijacked"}
        )
        assert resp.status_code == 404

    # Alice still sees her original prompt (not hijacked).
    _, alice_client = _client_for(session_factory, alice)
    async with alice_client:
        follow = await alice_client.get(f"{API}/alice-upd")
        assert follow.status_code == 200
        assert follow.json()["data"]["system_prompt"] == "x"


async def test_created_agent_records_owner_in_response(
    session_factory, users, tmp_path, monkeypatch
):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    alice, _ = users
    _, client = _client_for(session_factory, alice)
    async with client:
        resp = await client.post(
            f"{API}",
            json={
                "name": "owner-agent",
                "model": "gpt-4o",
                "system_prompt": "x",
                "allowed_tools": [],
                "max_tokens_budget": 1.0,
            },
        )
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["user_id"] == str(alice.id)
