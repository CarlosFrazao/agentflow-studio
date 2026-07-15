"""Testes TDD: Prompt Hydration aplicado na criação de cards (Item C).

Quando um card é criado com título em PT informal, o sistema hidrata o
prompt e persiste a versão enriquecida em meta['hydrated_prompt'], sem
perder o título original.
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def test_create_card_hydrates_portuguese_title_into_meta(client):
    # Cria projeto
    proj = await client.post(f"{API}/projects", json={"name": "Hydra Proj", "description": "x"})
    pid = proj.json()["data"]["id"]

    resp = await client.post(
        f"{API}/cards",
        json={"project_id": pid, "title": "faz um site de vendas com carrinho", "column": "backlog"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    meta = data.get("meta", {})
    assert "hydrated_prompt" in meta
    assert "e-commerce" in meta["hydrated_prompt"].lower()
    # título original preservado
    assert data["title"] == "faz um site de vendas com carrinho"


async def test_create_card_with_english_title_still_hydrates_rules(client):
    proj = await client.post(f"{API}/projects", json={"name": "Hydra Proj2", "description": "x"})
    pid = proj.json()["data"]["id"]

    resp = await client.post(
        f"{API}/cards",
        json={"project_id": pid, "title": "Build a payment API", "column": "backlog"},
    )
    assert resp.status_code == 201
    meta = resp.json()["data"].get("meta", {})
    assert "hydrated_prompt" in meta
    assert "GOVERNANCE" in meta["hydrated_prompt"]
