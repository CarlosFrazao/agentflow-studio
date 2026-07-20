"""Testes do grafo de preferências (Fase D1 / F-010).

Cobre ``build_graph`` (nós + arestas + co-ocorrência/sobreposição lexical) e
``mutate_preference`` (edit, remove/arquivar recuperável, restore).

Usa os fixtures ``engine`` / ``session_factory`` do conftest (SQLite em
memória, schema criado via ``Base.metadata.create_all``).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services.preference_graph import build_graph, mutate_preference

pytestmark = pytest.mark.asyncio


async def _make_user(session: AsyncSession, email: str = "graph@example.com") -> User:
    user = User(id=uuid4(), email=email, display_name="Graph", password_hash=None)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_prefs(
    session: AsyncSession, user_id, rows: list[tuple[str, str, int]]
) -> list[UserPreference]:
    objs: list[UserPreference] = []
    for attribute, value, confidence in rows:
        p = UserPreference(
            user_id=user_id,
            attribute=attribute,
            value=value,
            confidence_count=confidence,
            last_reinforced_at=datetime.now(tz=timezone.utc),
        )
        session.add(p)
        objs.append(p)
    await session.commit()
    for p in objs:
        await session.refresh(p)
    return objs


async def test_build_graph_returns_nodes_and_edges(session_factory):
    async with session_factory() as s:
        user = await _make_user(s)
        await _seed_prefs(
            s,
            user.id,
            [
                ("language", "pt-BR", 3),
                ("language", "en-US", 2),
                ("theme", "dark mode", 2),
            ],
        )

    async with session_factory() as s:
        graph = await build_graph(s)

    assert graph["stats"]["nodes"] == 3
    assert graph["stats"]["applied_nodes"] == 3  # todas com confidence >= 2
    # "language: pt-BR" e "language: en-US" co-ocorrem no mesmo atributo → 1 aresta
    assert graph["stats"]["edges"] >= 1
    # a aresta de co-ocorrência liga dois nós do mesmo atributo
    co_edge = next(
        (e for e in graph["edges"] if e["kind"] == "co_occurrence"), None
    )
    assert co_edge is not None


async def test_build_graph_lexical_overlap_links_similar_values(session_factory):
    async with session_factory() as s:
        user = await _make_user(s)
        await _seed_prefs(
            s,
            user.id,
            [
                ("framework", "react with typescript", 2),
                ("style", "react native styling", 2),
                ("other", "unrelated thing", 2),
            ],
        )

    async with session_factory() as s:
        graph = await build_graph(s)

    lexical = [e for e in graph["edges"] if e["kind"] == "lexical"]
    # "react with typescript" e "react native styling" compartilham tokens → aresta lexical
    assert any(e["weight"] >= 1 for e in lexical)


async def test_build_graph_filters_by_user(session_factory):
    async with session_factory() as s:
        u1 = await _make_user(s, "u1@example.com")
        u2 = await _make_user(s, "u2@example.com")
        await _seed_prefs(s, u1.id, [("language", "pt-BR", 3)])
        await _seed_prefs(s, u2.id, [("language", "en-US", 2)])

    async with session_factory() as s:
        g1 = await build_graph(s, user_id=u1.id)
        g2 = await build_graph(s, user_id=u2.id)

    assert g1["stats"]["nodes"] == 1
    assert g2["stats"]["nodes"] == 1
    assert g1["nodes"][0]["value"] == "pt-BR"
    assert g2["nodes"][0]["value"] == "en-US"


async def test_build_graph_empty_has_zero_stats(session_factory):
    async with session_factory() as s:
        graph = await build_graph(s)

    assert graph["stats"]["nodes"] == 0
    assert graph["stats"]["edges"] == 0
    assert graph["stats"]["isolated_pct"] == 0.0


async def test_mutate_remove_archives_recoverable(session_factory):
    async with session_factory() as s:
        user = await _make_user(s)
        prefs = await _seed_prefs(s, user.id, [("language", "pt-BR", 3)])
        pid = prefs[0].id

    # remove = arquivar (não deletar)
    async with session_factory() as s:
        updated = await mutate_preference(s, str(pid), "remove")
        assert updated.archived is True

        raw = await s.get(UserPreference, pid)
        assert raw is not None  # histórico físico preservado
        assert raw.archived is True

    # restore reverte o arquivamento
    async with session_factory() as s:
        restored = await mutate_preference(s, str(pid), "restore")
        assert restored.archived is False


async def test_mutate_edit_rewrites_value(session_factory):
    async with session_factory() as s:
        user = await _make_user(s)
        prefs = await _seed_prefs(s, user.id, [("language", "pt-BR", 3)])
        pid = prefs[0].id

    async with session_factory() as s:
        updated = await mutate_preference(s, str(pid), "edit", value="pt-BR formal")
        assert updated.value == "pt-BR formal"
        assert updated.archived is False

        raw = await s.get(UserPreference, pid)
        assert raw.value == "pt-BR formal"


async def test_mutate_unknown_preference_raises_not_found(session_factory):
    async with session_factory() as s:
        with pytest.raises(NotFoundError):
            await mutate_preference(s, str(uuid4()), "remove")


async def test_mutate_invalid_action_raises_validation_error(session_factory):
    async with session_factory() as s:
        user = await _make_user(s)
        prefs = await _seed_prefs(s, user.id, [("language", "pt-BR", 3)])
        pid = prefs[0].id

    async with session_factory() as s:
        with pytest.raises(ValidationError):
            await mutate_preference(s, str(pid), "explode")


async def test_mutate_edit_empty_value_raises_validation_error(session_factory):
    async with session_factory() as s:
        user = await _make_user(s)
        prefs = await _seed_prefs(s, user.id, [("language", "pt-BR", 3)])
        pid = prefs[0].id

    async with session_factory() as s:
        with pytest.raises(ValidationError):
            await mutate_preference(s, str(pid), "edit", value="   ")


async def test_mutate_cross_user_raises_not_found(session_factory):
    """FEAT-001 (B9-3): user A cannot mutate a preference owned by user B.

    Gherkin 4.1.2 — `Dado` uma preferência de outro usuário, `Quando`
    `mutate_preference` é chamado com esse id e `user_id` diferente, `Então`
    levanta `NotFoundError`.
    """
    async with session_factory() as s:
        owner = await _make_user(s, "owner@example.com")
        other = await _make_user(s, "intruder@example.com")
        prefs = await _seed_prefs(s, owner.id, [("language", "pt-BR", 3)])
        pid = prefs[0].id

    # Intruder calls mutate with owner's preference id but its own user_id.
    async with session_factory() as s:
        with pytest.raises(NotFoundError):
            await mutate_preference(
                s, str(pid), "edit", value="hijacked", user_id=other.id
            )
        # Resource of the victim is untouched.
        raw = await s.get(UserPreference, pid)
        assert raw.value == "pt-BR"
        assert raw.archived is False


async def test_mutate_null_user_id_raises_not_found(session_factory):
    """FEAT-001 edge case: calling the engine without owner match fails.

    Gherkin 4.1.3 — user_id nulo/incompatível → NotFoundError (dono não casado).
    """
    async with session_factory() as s:
        user = await _make_user(s)
        prefs = await _seed_prefs(s, user.id, [("language", "pt-BR", 3)])
        pid = prefs[0].id

    async with session_factory() as s:
        with pytest.raises(NotFoundError):
            await mutate_preference(
                s, str(pid), "edit", value="x", user_id=uuid4()
            )

