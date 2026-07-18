"""FEAT-007: protege GET /share/{project_id} com JWT + ownership (P1).

Antes: a rota era PUBLICA — qualquer cliente que soubesse um project_id
alheio lia o board (OWASP API1 / BOLA). Agora exige o JWT do proprietario
do projeto; UUIDs de outros donos retornam 404 (sem vazar a existencia).
"""

import pytest

from app.api.v1.share import build_shared_board

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
    """Sobrescreve get_current_user para o usuario informado."""
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


async def _seed_project(client, owner_id: str, session_factory, name: str) -> str:
    await _login_as(client, owner_id, session_factory)
    resp = await client.post(f"{API}/projects", json={"name": name, "description": "x"})
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_share_requires_auth(anon_client, session_factory) -> None:
    # project_id valido, mas SEM token -> 401 (guarda real ativa).
    resp = await anon_client.get(f"{API}/share/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


async def test_share_owner_ok(client, session_factory) -> None:
    owner = await _register(client, "feat007-owner@example.com")
    pid = await _seed_project(client, owner, session_factory, "ShareProj")
    await client.post(f"{API}/cards", json={"project_id": pid, "title": "C1", "column": "backlog"})
    await client.post(f"{API}/cards", json={"project_id": pid, "title": "C2", "column": "done"})

    await _login_as(client, owner, session_factory)
    resp = await client.get(f"{API}/share/{pid}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["project_id"] == pid
    titles = [c["title"] for col in data["columns"].values() for c in col]
    assert "C1" in titles and "C2" in titles


async def test_share_non_owner_404(client, session_factory) -> None:
    owner = await _register(client, "feat007-owner2@example.com")
    other = await _register(client, "feat007-other@example.com")
    pid = await _seed_project(client, owner, session_factory, "ShareProjB")

    # Logamos como OUTRO usuario e tentamos ler o board do dono -> 404.
    await _login_as(client, other, session_factory)
    resp = await client.get(f"{API}/share/{pid}")
    assert resp.status_code == 404


async def test_shared_board_unknown_project_404(client, session_factory) -> None:
    await _register(client, "feat007-anon@example.com")
    resp = await client.get(f"{API}/share/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_build_shared_board_groups_by_column() -> None:
    class FakeCard:
        def __init__(self, title, column):
            self.title = title
            self.column = column
            self.id = title
            self.meta = {}

    cards = [FakeCard("a", "backlog"), FakeCard("b", "done")]
    board = build_shared_board("proj-1", cards, [])
    assert board["project_id"] == "proj-1"
    assert [c["title"] for c in board["columns"]["backlog"]] == ["a"]
    assert [c["title"] for c in board["columns"]["done"]] == ["b"]
