"""Tarefa B — cabeamento de record_lesson nos agents (D2).

Garante que lições de falha/degradação são gravadas em agent_lessons.md
via LearningMemory().record_lesson, disparado a partir do run_card e dos
agents, sem quebrar o pipeline se o arquivo for ilegível.
"""

from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.deps import get_current_user, get_owned_card, get_session
from app.core.config import Settings
from app.main import create_app
from app.models.card import Card
from app.models.project import Project
from app.models.user import User as UserModel
from app.services.learning_memory import LearningMemory, LESSONS_PATH


def _seed_lessons_path(tmp_path: Path, monkeypatch) -> Path:
    """Aponta LESSONS_PATH do módulo para um arquivo temporário."""
    target = tmp_path / "data" / "agent_lessons.md"
    monkeypatch.setattr(
        "app.services.learning_memory.LESSONS_PATH", target
    )
    return target


async def _make_app_with_card(
    session_factory, tmp_path, monkeypatch, *, column: str
):
    """Cria app + card real e aplica overrides (auth, session, owned_card)."""
    app = create_app()
    target = _seed_lessons_path(tmp_path, monkeypatch)

    async with session_factory() as s:
        user = UserModel(
            id=UUID(int=7),
            email="lessons@example.com",
            display_name="Lessons",
            password_hash=None,
        )
        project = Project(id=UUID(int=8), name="p", description="", user_id=user.id)
        card = Card(
            id=UUID(int=9),
            project_id=project.id,
            title="idea-cabeada",
            column=column,
        )
        s.add_all([user, project, card])
        await s.commit()
        card_id = card.id

    async def override_session():
        async with session_factory() as s:
            yield s

    async def override_owned_card():
        async with session_factory() as s:
            return await s.get(Card, card_id)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_owned_card] = override_owned_card
    return app, card_id, target


def test_record_lesson_persists_to_file(tmp_path, monkeypatch):
    """RED/GREEN base: record_lesson escreve a lição no arquivo alvo."""
    target = _seed_lessons_path(tmp_path, monkeypatch)
    LearningMemory().record_lesson("research", "SRA indisponível")
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "[research]" in content
    assert "SRA indisponível" in content


@pytest.mark.asyncio
async def test_run_card_records_lesson_on_agent_failure(
    session_factory, tmp_path, monkeypatch
):
    """run_card grava lição quando o dispatch levanta (except do agente)."""
    app, card_id, target = await _make_app_with_card(
        session_factory, tmp_path, monkeypatch, column="researching"
    )

    # Força o dispatch a falhar DENTRO do try do run_card: o ResearchAgent.run
    # levanta (simula SRA caindo durante a execução do agente).
    async def boom_run(self, query, mode="guerrilha"):
        raise RuntimeError("sra connection refused")

    monkeypatch.setattr(
        "app.api.v1.run.ResearchAgent.run", boom_run
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(f"/api/v1/cards/{card_id}/run")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["status"] == "failed"

    # Lição deve ter sido gravada no arquivo temporário.
    assert target.exists(), "lição não foi gravada"
    content = target.read_text(encoding="utf-8")
    assert "[research]" in content
    assert "sra connection refused" in content


@pytest.mark.asyncio
async def test_run_card_does_not_record_on_success(
    session_factory, tmp_path, monkeypatch
):
    """Sem falha de agente, nenhuma lição é gravada (apenas em falha)."""
    app, card_id, target = await _make_app_with_card(
        session_factory, tmp_path, monkeypatch, column="done"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(f"/api/v1/cards/{card_id}/run")

    assert resp.status_code == 200
    if target.exists():
        assert target.read_text(encoding="utf-8").strip() == ""
