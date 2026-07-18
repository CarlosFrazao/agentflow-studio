"""Testes TDD dos routers de Snippets (F-009), Preferences (F-010) e Budget (F-011)."""

import pytest
from httpx import AsyncClient
from uuid import UUID

pytestmark = pytest.mark.asyncio


async def _login_as(client: AsyncClient, user_id: str, session_factory) -> None:
    """Sobrescreve get_current_user para o usuario informado (path e ignorado)."""
    from app.api.v1.deps import get_current_user
    from app.models.user import User

    async with session_factory() as s:
        db_user = await s.get(User, UUID(user_id))
        assert db_user is not None

        async def override() -> User:
            return db_user

    client._transport.app.dependency_overrides[get_current_user] = override


async def _set_spend(user_id: str, amount: float, session_factory) -> None:
    """Semeia gasto acumulado direto no banco (FEAT-002: spend nao e settable
    via API; simula o que as Executions fariam)."""
    from app.models.budget import BudgetLimit
    from sqlalchemy import select

    async with session_factory() as s:
        budget = await s.scalar(
            select(BudgetLimit).where(BudgetLimit.user_id == UUID(user_id))
        )
        if budget is None:
            budget = BudgetLimit(user_id=UUID(user_id))
            s.add(budget)
        budget.current_month_spend_usd = amount
        await s.commit()


async def _create_user(client: AsyncClient) -> str:
    # FEAT-C001: router /users (CRUD de User) removido para eliminar IDOR.
    # Usuarios sao criados via /auth/register (envelope {data: {user: {id}}}).
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "u@ex.com", "display_name": "U", "password": "secret123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["user"]["id"]


# ---- F-009 Snippets ----
async def test_create_snippet_requires_license(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    # sem campo license -> 422
    resp = await client.post(
        "/api/v1/snippets",
        json={"title": "S", "content": "x", "language": "py"},
    )
    assert resp.status_code == 422


async def test_create_snippet_with_copyleft_flag(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    resp = await client.post(
        "/api/v1/snippets",
        json={
            "title": "GPL lib",
            "content": "x",
            "language": "py",
            "license": "GPL",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["license"] == "GPL"
    # FEAT-004: o dono e o usuario autenticado, nunca o user_id do body (ignorado).
    assert str(resp.json()["data"]["user_id"]) == uid


async def test_list_snippets_by_user(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    await client.post(
        "/api/v1/snippets",
        json={"title": "A", "content": "x", "license": "MIT"},
    )
    # FEAT-004: lista apenas os snippets do dono autenticado (sem filtro por query).
    resp = await client.get("/api/v1/snippets")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


# ---- F-010 Preferences ----
async def test_preference_applied_only_when_confidence_ge_2(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
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


async def test_get_preferences_returns_list(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    await client.post(
        "/api/v1/users/{uid}/preferences".format(uid=uid),
        json={"attribute": "lang", "value": "pt"},
    )
    resp = await client.get(f"/api/v1/users/{uid}/preferences")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


# ---- F-011 Budget ----
async def test_budget_defaults_and_update(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    resp = await client.get(f"/api/v1/users/{uid}/budget")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["monthly_limit_usd"] == 10.0
    assert data["per_project_limit_usd"] == 3.0


async def test_budget_warning_at_80_percent(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    await client.put(
        f"/api/v1/users/{uid}/budget",
        json={"monthly_limit_usd": 10.0, "per_project_limit_usd": 3.0},
    )
    await _set_spend(uid, 8.5, session_factory)  # gasto real (nao settable via API)
    resp = await client.get(f"/api/v1/users/{uid}/budget")
    assert resp.json()["data"]["warning_level"] == "warning"  # 85% > 80%


async def test_budget_blocked_at_100_percent(
    client: AsyncClient, session_factory
) -> None:
    uid = await _create_user(client)
    await _login_as(client, uid, session_factory)
    await client.put(
        f"/api/v1/users/{uid}/budget",
        json={"monthly_limit_usd": 10.0, "per_project_limit_usd": 3.0},
    )
    await _set_spend(uid, 10.0, session_factory)  # gasto real (nao settable via API)
    resp = await client.get(f"/api/v1/users/{uid}/budget")
    assert resp.json()["data"]["warning_level"] == "blocked"  # 100%
