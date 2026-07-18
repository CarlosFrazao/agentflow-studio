"""FEAT-003: isolamento de artifacts por dono do card (IDOR, P0).

Valida que um usuario logado so pode ler/criar artifacts de cards cujo Project
pai lhe pertence. Antes da correcao, /cards/{card_id}/artifacts so checava a
existencia do Card (session.get), permitindo que qualquer usuario logado
enumerasse UUIDs alheios (Broken Object Level Authorization).
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


async def _create_card(client, uid: str, session_factory) -> str:
    """Cria um Project + Card para o usuario logado e devolve o card_id."""
    await _login_as(client, uid, session_factory)
    proj = await client.post(f"{API}/projects", json={"name": "P"})
    assert proj.status_code == 201, proj.text
    pid = proj.json()["data"]["id"]
    card = await client.post(
        f"{API}/cards",
        json={"project_id": pid, "title": "Ideia", "column": "backlog"},
    )
    assert card.status_code == 201, card.text
    return card.json()["data"]["id"]


async def test_artifact_cross_user_forbidden(client, session_factory):
    a = await _register(client, "feat003-a@example.com")
    b = await _register(client, "feat003-b@example.com")

    # B possui um card
    card_b = await _create_card(client, b, session_factory)

    # A loga e tenta LISTAR os artifacts do card de B -> 404 (ownership negado)
    await _login_as(client, a, session_factory)
    resp = await client.get(f"{API}/cards/{card_b}/artifacts")
    assert resp.status_code == 404  # sem vazar existencia do recurso alheio


async def test_artifact_cross_user_create_forbidden(client, session_factory):
    a = await _register(client, "feat003-ca@example.com")
    b = await _register(client, "feat003-cb@example.com")

    card_b = await _create_card(client, b, session_factory)

    # A tenta CRIAR artifact no card de B -> 404
    await _login_as(client, a, session_factory)
    resp = await client.post(
        f"{API}/cards/{card_b}/artifacts",
        json={"agent_name": "dev", "type": "code", "content": "x"},
    )
    assert resp.status_code == 404


async def test_artifact_own_list_ok(client, session_factory):
    a = await _register(client, "feat003-own@example.com")
    card_a = await _create_card(client, a, session_factory)

    # A cria um artifact no proprio card
    created = await client.post(
        f"{API}/cards/{card_a}/artifacts",
        json={"agent_name": "dev", "type": "code", "content": "print(1)"},
    )
    assert created.status_code == 201, created.text

    # A lista os proprios artifacts -> 200 com o item criado
    listed = await client.get(f"{API}/cards/{card_a}/artifacts")
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert any(item["id"] == created.json()["data"]["id"] for item in items)
