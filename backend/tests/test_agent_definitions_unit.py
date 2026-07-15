"""Testes unitários do serviço agent_definitions (Item 5 — cobertura).

Exercita a lógica pura do serviço (list/update/delete) com sessão SQLite
em memória, sem depender da API.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.models import Base
from app.models.agent import Agent as AgentModel
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services import agent_definitions as svc

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_create_and_list_agent(session, tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    payload = AgentCreate(
        name="unit-agent",
        model="gpt-4o",
        system_prompt="x",
        allowed_tools=["read_file"],
        max_tokens_budget=1.0,
    )
    created = await svc.create_agent(payload, session)
    assert created.name == "unit-agent"
    listed = await svc.list_agents(session)
    assert len(listed) == 1
    assert listed[0].model == "gpt-4o"
    # YAML espelhado
    assert (tmp_path / "unit-agent.yaml").exists()


async def test_update_agent_changes_fields(session, tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    payload = AgentCreate(
        name="upd-unit",
        model="gpt-4o",
        system_prompt="old",
        allowed_tools=[],
        max_tokens_budget=1.0,
    )
    await svc.create_agent(payload, session)
    updated = await svc.update_agent_by_name(
        "upd-unit", AgentUpdate(system_prompt="new", max_tokens_budget=2.0), session
    )
    assert updated.system_prompt == "new"
    assert updated.max_tokens_budget == 2.0


async def test_delete_agent_removes_record_and_yaml(session, tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    payload = AgentCreate(
        name="del-unit",
        model="gpt-4o",
        system_prompt="x",
        allowed_tools=[],
        max_tokens_budget=1.0,
    )
    await svc.create_agent(payload, session)
    await svc.delete_agent_by_name("del-unit", session)
    assert await svc.get_agent_by_name("del-unit", session) is None
    assert not (tmp_path / "del-unit.yaml").exists()
