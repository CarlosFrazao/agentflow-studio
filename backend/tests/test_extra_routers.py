"""Testes TDD dos routers de Snippets (F-009), Preferences (F-010) e Budget (F-011)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_user(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/users", json={"email": "u@ex.com", "display_name": "U"}
    )
    return resp.json()["data"]["id"]


# ---- F-009 Snippets ----
async def test_create_snippet_requires_license(client: AsyncClient) -> None:
    uid = await _create_user(client)
    # sem campo license -> 422
    resp = await client.post(
        "/api/v1/snippets",
        json={"user_id": uid, "title": "S", "content": "x", "language": "py"},
    )
    assert resp.status_code == 422


async def test_create_snippet_with_copyleft_flag(client: AsyncClient) -> None:
    uid = await _create_user(client)
    resp = await client.post(
        "/api/v1/snippets",
        json={
            "user_id": uid,
            "title": "GPL lib",
            "content": "x",
            "language": "py",
            "license": "GPL",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["license"] == "GPL"


async def test_list_snippets_by_user(client: AsyncClient) -> None:
    uid = await _create_user(client)
    await client.post(
        "/api/v1/snippets",
        json={"user_id": uid, "title": "A", "content": "x", "license": "MIT"},
    )
    resp = await client.get(f"/api/v1/snippets?user_id={uid}")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


# ---- F-010 Preferences ----
async def test_preference_applied_only_when_confidence_ge_2(client: AsyncClient) -> None:
    uid = await _create_user(client)
    # reforca 1x -> confidence_count=1, nao aplicada
    r1 = await client.post(
        "/api/v1/users/{uid}/preferences".format(uid=uid),
        json={"attribute": "preferred_testing_framework", "value": "jest"},
    )
    assert r1.status_code == 201
    assert r1.json()["data"]["confidence_count"] == 1
    assert r1.json()["data"]["applied"] is False
    # reforca 2x -> confidence_count=2, aplicada
    r2 = await client.post(
        "/api/v1/users/{uid}/preferences".format(uid=uid),
        json={"attribute": "preferred_testing_framework", "value": "jest"},
    )
    assert r2.json()["data"]["confidence_count"] == 2
    assert r2.json()["data"]["applied"] is True


async def test_get_preferences_returns_list(client: AsyncClient) -> None:
    uid = await _create_user(client)
    await client.post(
        "/api/v1/users/{uid}/preferences".format(uid=uid),
        json={"attribute": "lang", "value": "pt"},
    )
    resp = await client.get(f"/api/v1/users/{uid}/preferences")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


# ---- F-011 Budget ----
async def test_budget_defaults_and_update(client: AsyncClient) -> None:
    uid = await _create_user(client)
    resp = await client.get(f"/api/v1/users/{uid}/budget")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["monthly_limit_usd"] == 10.0
    assert data["per_project_limit_usd"] == 3.0


async def test_budget_warning_at_80_percent(client: AsyncClient) -> None:
    uid = await _create_user(client)
    await client.put(
        f"/api/v1/users/{uid}/budget",
        json={"monthly_limit_usd": 10.0, "per_project_limit_usd": 3.0,
              "current_month_spend_usd": 8.5},
    )
    resp = await client.get(f"/api/v1/users/{uid}/budget")
    assert resp.json()["data"]["warning_level"] == "warning"  # 85% > 80%


async def test_budget_blocked_at_100_percent(client: AsyncClient) -> None:
    uid = await _create_user(client)
    await client.put(
        f"/api/v1/users/{uid}/budget",
        json={"monthly_limit_usd": 10.0, "per_project_limit_usd": 3.0,
              "current_month_spend_usd": 10.0},
    )
    resp = await client.get(f"/api/v1/users/{uid}/budget")
    assert resp.json()["data"]["warning_level"] == "blocked"  # 100%
