"""Bloco 8 (FEAT-008): Qualidade & Hardening — testes de tenant scope e config.

Cobre:
- firecrawl_api_key opcional (A-3)
- dashboard restrito ao usuário (F-5 / tenant scope)
- metrics restritas ao usuário (F-5)
- get_owned_card eager-load do project (A-4 / N+1)
- classificação de licença unicode-safe (D-1)
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.deps import get_current_user
from app.core.config import get_settings
from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project
from app.models.user import User
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# A-3: firecrawl_api_key opcional
# ---------------------------------------------------------------------------


def test_config_firecrawl_key_optional() -> None:
    settings = get_settings()
    # Default é None (self-hosted sem auth em dev). Nunca um placeholder fixo.
    assert settings.firecrawl_api_key is None


# ---------------------------------------------------------------------------
# D-1: classificação de licença unicode-safe
# ---------------------------------------------------------------------------


def test_classify_license_unicode_safe() -> None:
    """Unicode casing que expande (ß -> SS) não quebra a janela de contexto.

    O texto original contém "ß" (sharp s) que vira "SS" em .upper(); se a
    janela fosse fatiada de `text` (não de `upper`), os índices desalinhavam
    e o termo de contexto de licença seria perdido. Aqui o acento/unicode
    está colado ao "GPL-3.0" para forçar o alinhamento.
    """
    from app.services.agents.code_research import CodeResearchAgent

    # "GPL-3.0" cercado por um caractere que expande em .upper() (ß / é) e
    # por um termo de contexto de licença (SPDX) para confirmar copyleft.
    text = "SPDX-License-Identifier: GPL-3.0-or-later straße"  # 'straße' -> 'STRASSE'
    cls = CodeResearchAgent._classify_license(text)
    assert cls == "copyleft"


def test_classify_license_mention_not_copyleft_unicode() -> None:
    """Menção solta de GPL em texto unicode continua não-copyleft."""
    from app.services.agents.code_research import CodeResearchAgent

    text = "unsere bibliothek ist schneller als die alte GPL-basierte implementation"
    cls = CodeResearchAgent._classify_license(text)
    assert cls != "copyleft"


# ---------------------------------------------------------------------------
# A-4: get_owned_card eager-load do project (evita N+1)
# ---------------------------------------------------------------------------


async def test_get_owned_card_eager_loads_project(
    client, session_factory: async_sessionmaker
) -> None:
    """get_owned_card popula card.project sem query extra (selectinload)."""
    from app.api.v1.deps import get_owned_card

    user = await _current_user(client)
    async with session_factory() as s:
        project = Project(name="P1", user_id=user.id)
        s.add(project)
        await s.commit()
        await s.refresh(project)
        card = Card(project_id=project.id, title="C1", column="backlog")
        s.add(card)
        await s.commit()
        await s.refresh(card)
        card_id = card.id

    # Injeta o card via dependência (exercita get_owned_card diretamente).
    async with session_factory() as s:
        loaded = await get_owned_card(card_id, user=user, session=s)
        assert loaded.project is not None
        assert loaded.project.id == project.id


# ---------------------------------------------------------------------------
# F-5: dashboard + metrics restritos ao usuário
# ---------------------------------------------------------------------------


async def test_dashboard_own_only(
    client, session_factory: async_sessionmaker
) -> None:
    """Dashboard de A não vaza projetos/execuções de B."""
    user_a = await _current_user(client)
    user_b = await _seed_user(session_factory, "user-b@example.com")

    async with session_factory() as s:
        # Projeto + execução de B (não devem aparecer para A).
        proj_b = Project(name="ProjB", user_id=user_b.id)
        s.add(proj_b)
        await s.commit()
        await s.refresh(proj_b)
        card_b = Card(project_id=proj_b.id, title="CB", column="done")
        s.add(card_b)
        await s.commit()
        await s.refresh(card_b)
        s.add(
            Execution(
                card_id=card_b.id,
                agent_name="dev",
                cost_usd=9.99,
                status="success",
                started_at=datetime.now(tz=timezone.utc),
            )
        )
        # Projeto + execução de A (devem aparecer).
        proj_a = Project(name="ProjA", user_id=user_a.id)
        s.add(proj_a)
        await s.commit()
        await s.refresh(proj_a)
        card_a = Card(project_id=proj_a.id, title="CA", column="backlog")
        s.add(card_a)
        await s.commit()
        await s.refresh(card_a)
        s.add(
            Execution(
                card_id=card_a.id,
                agent_name="dev",
                cost_usd=1.50,
                status="success",
                started_at=datetime.now(tz=timezone.utc),
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # A só enxerga o próprio projeto.
    assert data["projects_created"] == 1
    # Total de custo reflete só A (1.50), não o global (11.49).
    assert data["total_cost_usd"] == 1.5


async def test_metrics_own_only(
    client, session_factory: async_sessionmaker
) -> None:
    """Insights de A não incluem custo de projeto de B."""
    user_a = await _current_user(client)
    user_b = await _seed_user(session_factory, "user-b2@example.com")

    async with session_factory() as s:
        proj_b = Project(name="ProjB", user_id=user_b.id)
        s.add(proj_b)
        await s.commit()
        await s.refresh(proj_b)
        card_b = Card(project_id=proj_b.id, title="CB", column="done")
        s.add(card_b)
        await s.commit()
        await s.refresh(card_b)
        s.add(
            Execution(
                card_id=card_b.id,
                agent_name="dev",
                cost_usd=50.0,
                status="success",
                started_at=datetime.now(tz=timezone.utc),
            )
        )
        proj_a = Project(name="ProjA", user_id=user_a.id)
        s.add(proj_a)
        await s.commit()
        await s.refresh(proj_a)
        card_a = Card(project_id=proj_a.id, title="CA", column="backlog")
        s.add(card_a)
        await s.commit()
        await s.refresh(card_a)
        s.add(
            Execution(
                card_id=card_a.id,
                agent_name="dev",
                cost_usd=2.0,
                status="success",
                started_at=datetime.now(tz=timezone.utc),
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/metrics/insights?days=365")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_cost_usd"] == 2.0
    # Só o projeto de A aparece no custo por projeto.
    assert len(data["cost_by_project"]) == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _current_user(client) -> User:
    """Recupera o usuário autenticado pelo override do fixture `client`."""
    override = client._transport.app.dependency_overrides.get(get_current_user)
    return await override()


async def _seed_user(session_factory: async_sessionmaker, email: str) -> User:
    from uuid import uuid4

    async with session_factory() as s:
        user = User(id=uuid4(), email=email, display_name=email, password_hash=None)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        await s.refresh(user, attribute_names=["id", "email", "display_name"])
        return User(id=user.id, email=user.email, display_name=user.display_name)
