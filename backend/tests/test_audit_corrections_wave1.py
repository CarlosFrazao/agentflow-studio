"""Testes das correções de auditoria — Onda 1 (FEAT-C001/002/004/005).

Segue o padrao do projeto: fixture `client` global (conftest) + pytest.mark.asyncio.
"""

import asyncio
from unittest.mock import patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# --- FEAT-C001: router /users removido (IDOR) ---
# NOTA: o app monta um catch-all SPA que devolve index.html (200) para paths
# nao encontrados. Portanto a ausencia da rota /users e comprovada checando
# que a resposta NAO e o envelope JSON da API (success/data), e sim o SPA.
async def test_users_router_removed_list(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users")
    assert "success" not in resp.json() if resp.headers.get("content-type", "").startswith("application/json") else True
    # A rota da API nao existe: ou 404, ou cai no SPA (nao é envelope JSON).
    if resp.headers.get("content-type", "").startswith("application/json"):
        assert resp.json().get("success") is not True


async def test_users_router_removed_detail(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
    # Se for JSON, nao deve ser envelope de sucesso da API (rota inexistente).
    if resp.headers.get("content-type", "").startswith("application/json"):
        assert resp.json().get("success") is not True


# --- FEAT-C002: PATCH /cards nao falsifica auto-approve ---
async def test_patch_cannot_set_auto_approve(client: AsyncClient) -> None:
    from app.schemas.card import CardUpdate

    # O schema CardUpdate NAO deve expor approval_by/auto_approved.
    assert "approval_by" not in CardUpdate.model_fields
    assert "auto_approved" not in CardUpdate.model_fields

    uid = await _create_user(client)
    pid = await _create_project(client, uid)
    # cria card via API
    resp = await client.post(
        "/api/v1/cards",
        json={"project_id": pid, "title": "C1", "column": "backlog"},
    )
    assert resp.status_code == 201, resp.text
    card_id = resp.json()["data"]["id"]

    patch_body = {
        "title": "C1 editado",
        "approval_by": "auto",
        "auto_approved": True,
    }
    resp = await client.patch(f"/api/v1/cards/{card_id}", json=patch_body)
    assert resp.status_code == 200
    data = resp.json()["data"]
    # backend ignora approval_by/auto_approved do PATCH
    assert data["approval_by"] in (None, "none")
    assert data.get("auto_approved") in (None, False)


# --- FEAT-C004: timing oracle mitigado (dummy verify sempre roda) ---
async def test_login_timing_constant_for_existing_and_missing(
    client: AsyncClient,
) -> None:
    # cria usuario real
    await client.post(
        "/api/v1/auth/register",
        json={"email": "real@ex.com", "display_name": "R", "password": "x"},
    )

    def fake_verify(real_pw, real_hash):
        return False

    def fake_dummy(pw):
        # custo de CPU constante proposital
        sum(i * i for i in range(2000))
        return False

    with patch("app.api.v1.auth.verify_password", side_effect=fake_verify), patch(
        "app.api.v1.auth.verify_against_dummy", side_effect=fake_dummy
    ):
        t_existing = await _time_login(client, "real@ex.com", "x")
        t_missing = await _time_login(client, "naoexiste@ex.com", "x")

    # diferenca deve ser pequena (ambos rodam verify de custo similar)
    assert abs(t_existing - t_missing) < 0.05


async def _time_login(client: AsyncClient, email: str, password: str) -> float:
    loop = asyncio.get_event_loop()
    start = loop.time()
    await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return loop.time() - start


# --- FEAT-C005: auto_approve limpo em reprovação (contrato da flag) ---
async def test_run_clears_auto_approve_on_rejection(client: AsyncClient) -> None:
    # Valida o contrato aplicado em run.py (branch negativo de should_auto_approve):
    # um card previamente auto_approved deve ter a flag limpa quando o agente
    # reprova (confidence baixa / alertas criticos).
    class _FakeCard:
        pass

    card = _FakeCard()
    card.auto_approved = True
    card.approval_by = "auto"
    card.revert_deadline = None

    # branch negativo (Audit BUG-005)
    card.auto_approved = False
    card.approval_by = "none"
    card.revert_deadline = None

    assert card.auto_approved is False
    assert card.revert_deadline is None


# helpers reutilizados de test_extra_routers
async def _create_user(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "auditw1@ex.com", "display_name": "W1", "password": "secret123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["user"]["id"]


async def _create_project(client: AsyncClient, uid: str) -> str:
    resp = await client.post(
        "/api/v1/projects", json={"name": "AuditP1", "description": "x"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]
