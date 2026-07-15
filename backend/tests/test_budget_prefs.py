"""Testes dos endpoints /users/{id}/budget e /preferences (Item 5 — cobertura).

Usa o fixture `client`. Registra um usuário para obter um user_id válido.
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register_and_get_id(client):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "budget@example.com", "password": "T3st!Pass9", "display_name": "B"},
    )
    return resp.json()["data"]["user"]["id"]


async def test_get_budget_creates_default(client):
    uid = await _register_and_get_id(client)
    resp = await client.get(f"{API}/users/{uid}/budget")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["warning_level"] in ("ok", "warning", "blocked")


async def test_update_budget_sets_limit_and_level(client):
    uid = await _register_and_get_id(client)
    resp = await client.put(
        f"{API}/users/{uid}/budget",
        json={"monthly_limit_usd": 100.0, "current_month_spend_usd": 95.0},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["monthly_limit_usd"] == 100.0
    assert data["warning_level"] == "warning"  # 95% >= 80%


async def test_get_budget_unknown_user_404(client):
    resp = await client.get(f"{API}/users/00000000-0000-0000-0000-000000000000/budget")
    assert resp.status_code == 404


async def test_preferences_reinforce_and_list(client):
    uid = await _register_and_get_id(client)
    reinforce = await client.post(
        f"{API}/users/{uid}/preferences",
        json={"attribute": "language", "value": "pt-BR"},
    )
    assert reinforce.status_code == 201
    body = reinforce.json()["data"]
    assert body["attribute"] == "language"
    # Com 1 reforço, ainda não aplicado (threshold 2)
    assert body["applied"] is False
    listed = await client.get(f"{API}/users/{uid}/preferences")
    assert listed.status_code == 200
    assert any(p["attribute"] == "language" for p in listed.json()["data"])


async def test_preferences_unknown_user_404(client):
    resp = await client.post(
        f"{API}/users/00000000-0000-0000-0000-000000000000/preferences",
        json={"attribute": "x", "value": "y"},
    )
    assert resp.status_code == 404
