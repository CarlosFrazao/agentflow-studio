"""FEAT-002: isolamento de orcamento por dono (IDOR) + anti-fraude de gasto (P0).

Valida que um usuario logado so pode ler/editar SEU proprio orcamento e que o
campo financeiro current_month_spend_usd NUNCA e settable pelo cliente (impede
zerar o gasto e contornar o cap — fraude de orcamento).
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register(client, email: str) -> str:
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "T3st!Pass9", "display_name": "U"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["user"]["id"]


async def _login_as(client, user_id: str, session_factory) -> None:
    """Sobrescreve get_current_user para o usuario dono do user_id informado."""
    from uuid import UUID

    from app.api.v1.deps import get_current_user
    from app.models.user import User

    async with session_factory() as s:
        db_user = await s.get(User, UUID(user_id))
        assert db_user is not None

        async def override() -> User:
            return db_user

    app = client._transport.app  # ASGITransport expoe o app aqui
    app.dependency_overrides[get_current_user] = override


async def _set_spend(user_id: str, amount: float, session_factory) -> None:
    """Simula gasto acumulado direto no banco (como as Executions fariam)."""
    from uuid import UUID

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


async def test_budget_cross_user_forbidden(client, session_factory):
    a = await _register(client, "feat002-a@example.com")
    b = await _register(client, "feat002-b@example.com")

    # B define um limite proprio para materializar seu orcamento
    await _login_as(client, b, session_factory)
    resp_b = await client.put(
        f"{API}/users/{b}/budget", json={"monthly_limit_usd": 50.0}
    )
    assert resp_b.status_code == 200

    # A loga e tenta LER o orcamento de B pelo path — deve receber o de A (nao o de B)
    await _login_as(client, a, session_factory)
    resp = await client.get(f"{API}/users/{b}/budget")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert str(data["user_id"]) == a  # sempre o dono autenticado
    assert data["monthly_limit_usd"] != 50.0  # nao vazou o limite de B


async def test_budget_spend_not_settable(client, session_factory):
    a = await _register(client, "feat002-spend@example.com")
    await _set_spend(a, 9.0, session_factory)  # gasto real acumulado = 9.0

    await _login_as(client, a, session_factory)
    # Tenta fraudar: enviar current_month_spend_usd=0 junto do limite
    resp = await client.put(
        f"{API}/users/{a}/budget",
        json={"monthly_limit_usd": 10.0, "current_month_spend_usd": 0.0},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # O gasto permanece 9.0 (campo ignorado); nao foi zerado.
    assert data["current_month_spend_usd"] == 9.0
    assert data["monthly_limit_usd"] == 10.0
    assert data["warning_level"] == "warning"  # 90% >= 80%


async def test_budget_update_limit_ok(client, session_factory):
    a = await _register(client, "feat002-limit@example.com")
    await _login_as(client, a, session_factory)
    resp = await client.put(
        f"{API}/users/{a}/budget",
        json={"monthly_limit_usd": 100.0, "per_project_limit_usd": 25.0},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["monthly_limit_usd"] == 100.0
    assert data["per_project_limit_usd"] == 25.0
