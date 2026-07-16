"""Testes de regressão de autorização (P1 — IDOR / OWASP API1).

Garantem que um usuário autenticado NÃO consegue ler, editar ou
deletar recursos de outro usuário apenas enumerando UUIDs. O sistema
tem auth JWT multi-usuário ativa; estes testes trancam o filtro
por user_id em projects, cards, run e conversations.
"""

import pytest

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _register(client, email, pwd="T3st!Pass9"):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": pwd, "display_name": "U"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["access_token"]


async def _auth_client(client, token):
    """Devolve um wrapper que injeta o Bearer token em cada request."""
    from httpx import AsyncClient

    class _AuthClient:
        def __init__(self, base: AsyncClient, tk: str) -> None:
            self._c = base
            self._tk = tk

        async def _req(self, method, url, **kw):
            headers = dict(kw.pop("headers", {}))
            headers["Authorization"] = f"Bearer {self._tk}"
            return await self._c.request(method, url, headers=headers, **kw)

    return _AuthClient(client, token)


async def test_user_cannot_access_others_project(anon_client):
    tok_a = await _register(anon_client, "idora@example.com")
    tok_b = await _register(anon_client, "idorb@example.com")
    a = await _auth_client(anon_client, tok_a)
    b = await _auth_client(anon_client, tok_b)

    # A cria um project.
    resp = await a._req("POST", f"{API}/projects", json={"name": "Proj A"})
    assert resp.status_code == 201
    pid = resp.json()["data"]["id"]

    # B tenta acessar o project de A -> 404 (não 200, nem 403 que
    # vazaria a existência).
    resp = await b._req("GET", f"{API}/projects/{pid}")
    assert resp.status_code == 404

    # B tenta listar e NÃO deve ver o project de A.
    resp = await b._req("GET", f"{API}/projects")
    assert resp.status_code == 200
    assert all(item["id"] != pid for item in resp.json()["data"])

    # B tenta deletar o project de A -> 404.
    resp = await b._req("DELETE", f"{API}/projects/{pid}")
    assert resp.status_code == 404


async def test_user_cannot_access_others_card(anon_client):
    tok_a = await _register(anon_client, "idora2@example.com")
    tok_b = await _register(anon_client, "idorb2@example.com")
    a = await _auth_client(anon_client, tok_a)
    b = await _auth_client(anon_client, tok_b)

    proj = await a._req("POST", f"{API}/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]

    card = await a._req(
        "POST",
        f"{API}/cards",
        json={"project_id": pid, "title": "Card A", "column": "backlog"},
    )
    assert card.status_code == 201
    cid = card.json()["data"]["id"]

    # B acessa o card de A -> 404.
    resp = await b._req("GET", f"{API}/cards/{cid}")
    assert resp.status_code == 404

    # B roda o card de A -> 404 (run respeita posse).
    resp = await b._req("POST", f"{API}/cards/{cid}/run")
    assert resp.status_code == 404

    # B lista cards filtrando pelo project de A -> erro de project.
    resp = await b._req("GET", f"{API}/cards?project_id={pid}")
    assert resp.status_code == 404


async def test_user_cannot_access_others_conversation(anon_client):
    tok_a = await _register(anon_client, "idora3@example.com")
    tok_b = await _register(anon_client, "idorb3@example.com")
    a = await _auth_client(anon_client, tok_a)
    b = await _auth_client(anon_client, tok_b)

    proj = await a._req("POST", f"{API}/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]

    conv = await a._req("POST", f"{API}/conversations", json={"project_id": pid})
    assert conv.status_code == 200
    cid = conv.json()["data"]["id"]

    # B acessa a conversa de A -> 404.
    resp = await b._req("GET", f"{API}/conversations/{cid}/messages")
    assert resp.status_code == 404

    # B cria conversa apontando para o project de A -> 404.
    resp = await b._req("POST", f"{API}/conversations", json={"project_id": pid})
    assert resp.status_code == 404


async def test_user_sees_only_own_projects(anon_client):
    tok_a = await _register(anon_client, "idora4@example.com")
    tok_b = await _register(anon_client, "idorb4@example.com")
    a = await _auth_client(anon_client, tok_a)
    b = await _auth_client(anon_client, tok_b)

    await a._req("POST", f"{API}/projects", json={"name": "Only A"})
    resp = await b._req("GET", f"{API}/projects")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
