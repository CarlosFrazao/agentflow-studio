"""Testes TDD da API de agentes declarativos (Item A)."""

import pytest

from app.services import agent_definitions as svc

pytestmark = pytest.mark.asyncio

API = "/api/v1/agents"


@pytest.fixture
def isolated_agents_dir(tmp_path, monkeypatch):
    """Aponta a escrita de YAML para um diretório temporário nos testes."""
    monkeypatch.setattr(svc, "AGENTS_DIR", tmp_path)
    yield tmp_path


async def test_create_agent_returns_201_and_persists_yaml(client, isolated_agents_dir):
    payload = {
        "name": "reviewer-pt",
        "model": "claude-3-5-sonnet",
        "system_prompt": "Voce e um revisor tecnico.",
        "allowed_tools": ["read_file", "run_test"],
        "max_tokens_budget": 0.5,
    }
    resp = await client.post(f"{API}", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "reviewer-pt"
    # YAML espelhado em disco
    yaml_files = list(isolated_agents_dir.glob("*.yaml"))
    assert len(yaml_files) == 1


async def test_create_duplicate_agent_returns_409(client, isolated_agents_dir):
    payload = {
        "name": "dup-agent",
        "model": "gpt-4o",
        "system_prompt": "x",
        "allowed_tools": [],
        "max_tokens_budget": 1.0,
    }
    await client.post(f"{API}", json=payload)
    resp = await client.post(f"{API}", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_list_agents_returns_created(client, isolated_agents_dir):
    payload = {
        "name": "list-agent",
        "model": "deepseek-coder",
        "system_prompt": "x",
        "allowed_tools": ["write_file"],
        "max_tokens_budget": 0.2,
    }
    await client.post(f"{API}", json=payload)
    resp = await client.get(f"{API}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(a["name"] == "list-agent" for a in data)


async def test_get_agent_by_name(client, isolated_agents_dir):
    payload = {
        "name": "get-agent",
        "model": "gpt-4o",
        "system_prompt": "x",
        "allowed_tools": [],
        "max_tokens_budget": 1.0,
    }
    await client.post(f"{API}", json=payload)
    resp = await client.get(f"{API}/get-agent")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "get-agent"


async def test_get_unknown_agent_returns_404(client, isolated_agents_dir):
    resp = await client.get(f"{API}/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_update_agent(client, isolated_agents_dir):
    payload = {
        "name": "upd-agent",
        "model": "gpt-4o",
        "system_prompt": "old",
        "allowed_tools": [],
        "max_tokens_budget": 1.0,
    }
    await client.post(f"{API}", json=payload)
    resp = await client.put(
        f"{API}/upd-agent",
        json={"system_prompt": "new prompt", "max_tokens_budget": 2.0},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["system_prompt"] == "new prompt"
    assert body["max_tokens_budget"] == 2.0


async def test_delete_agent(client, isolated_agents_dir):
    payload = {
        "name": "del-agent",
        "model": "gpt-4o",
        "system_prompt": "x",
        "allowed_tools": [],
        "max_tokens_budget": 1.0,
    }
    await client.post(f"{API}", json=payload)
    resp = await client.delete(f"{API}/del-agent")
    assert resp.status_code == 204
    follow = await client.get(f"{API}/del-agent")
    assert follow.status_code == 404
