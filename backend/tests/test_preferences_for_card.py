"""Testes do débito D1: ``get_preferences_for_card`` (leitura síncrona).

Cria um banco SQLite físico temporário com a mesma estrutura de colunas usada
pela aplicação (users/projects/user_preferences) e valida que:
- só preferências ativas (``archived = 0``) e confirmadas (``confidence_count >= 2``)
  são retornadas;
- o filtro é por usuário dono do projeto do card;
- fail-open (retorna [] sem banco/projeto/usuário).
"""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.services import preference_graph as pg
from app.services.preference_graph import get_preferences_for_card


class _FakeCard:
    def __init__(self, project_id=None, meta: dict | None = None) -> None:
        if project_id is not None:
            self.project_id = project_id
        if meta is not None:
            self.meta = meta


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "agentflow.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE users (id TEXT PRIMARY KEY);
        CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT);
        CREATE TABLE user_preferences (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            attribute TEXT,
            value TEXT,
            confidence_count INTEGER,
            archived INTEGER,
            last_reinforced_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return db


def _point_settings_to(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    class _S:
        database_url = f"sqlite+aiosqlite:///{db.as_posix()}"

    monkeypatch.setattr(pg, "get_settings", lambda: _S())


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = _make_db(tmp_path)
    _point_settings_to(monkeypatch, db)

    user_id = uuid4().hex
    project_id = uuid4().hex

    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO users (id) VALUES (?)", (user_id,))
    conn.execute(
        "INSERT INTO projects (id, user_id) VALUES (?, ?)", (project_id, user_id)
    )
    rows = [
        # (attribute, value, confidence, archived) -> só as 2 primeiras contam
        ("theme", "tema escuro", 3, 0),
        ("language", "python typed", 2, 0),
        ("framework", "so-1-evento", 1, 0),  # confidence < 2 -> excluída
        ("editor", "arquivada", 5, 1),       # archived -> excluída
    ]
    for attr, val, conf, arch in rows:
        conn.execute(
            "INSERT INTO user_preferences "
            "(id, user_id, attribute, value, confidence_count, archived, last_reinforced_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid4().hex, user_id, attr, val, conf, arch, "2026-07-14T00:00:00"),
        )
    conn.commit()
    conn.close()
    return {"project_id": project_id, "user_id": user_id}


def test_returns_only_active_confirmed_prefs(seeded) -> None:
    card = _FakeCard(project_id=seeded["project_id"])
    prefs = get_preferences_for_card(card)
    assert "theme: tema escuro" in prefs
    assert "language: python typed" in prefs
    assert not any("so-1-evento" in p for p in prefs)  # confidence < 2
    assert not any("arquivada" in p for p in prefs)     # archived


def test_project_id_via_meta(seeded) -> None:
    card = _FakeCard(meta={"project_id": seeded["project_id"]})
    prefs = get_preferences_for_card(card)
    assert len(prefs) == 2


def test_accepts_hyphenated_uuid(seeded, monkeypatch) -> None:
    from uuid import UUID

    hyphenated = str(UUID(seeded["project_id"]))
    card = _FakeCard(project_id=hyphenated)
    prefs = get_preferences_for_card(card)
    assert len(prefs) == 2


def test_returns_empty_without_project(seeded) -> None:
    assert get_preferences_for_card(_FakeCard()) == []


def test_returns_empty_for_unknown_project(seeded) -> None:
    card = _FakeCard(project_id=uuid4().hex)
    assert get_preferences_for_card(card) == []


def test_fail_open_when_db_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _point_settings_to(monkeypatch, tmp_path / "nonexistent.db")
    card = _FakeCard(project_id=uuid4().hex)
    assert get_preferences_for_card(card) == []


def test_no_forbidden_ecosystem_token_in_module() -> None:
    source = Path(pg.__file__).read_text(encoding="utf-8").lower()
    forbidden = "he" + "rmes"
    assert forbidden not in source
