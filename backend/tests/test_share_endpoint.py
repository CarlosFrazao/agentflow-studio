"""Testes TDD do compartilhamento de sessão via URL (Item D do analise_omnigent.md).

- Endpoint REST público /share/{project_id} expõe o board (cards por coluna)
  e execuções recentes, sem exigir JWT.
- Helper de serialização do board reutilizável pelo WebSocket.
"""

import pytest

from app.api.v1.share import build_shared_board

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _seed_project_with_cards(client):
    proj = await client.post(f"{API}/projects", json={"name": "ShareProj", "description": "x"})
    pid = proj.json()["data"]["id"]
    await client.post(f"{API}/cards", json={"project_id": pid, "title": "C1", "column": "backlog"})
    await client.post(f"{API}/cards", json={"project_id": pid, "title": "C2", "column": "done"})
    return pid


async def test_shared_board_is_public_no_jwt(client) -> None:
    pid = await _seed_project_with_cards(client)
    # sem token de auth
    resp = await client.get(f"{API}/share/{pid}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "columns" in data
    assert data["project_id"] == pid
    titles = [c["title"] for col in data["columns"].values() for c in col]
    assert "C1" in titles and "C2" in titles


async def test_shared_board_unknown_project_404(client) -> None:
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
