"""Testes TDD da memória de aprendizado incremental (Fase D2).

Cobre o round-trip ``record_lesson`` / ``recall_lessons`` (persistência em
markdown local), isolamento por agente, limite ``k``, e o auxiliar
``get_lessons_for_card`` que extrai o agente do card.

Usa arquivos temporários (fixtures ``tmp_path``) para não tocar o markdown
real em ``backend/data/agent_lessons.md``.
"""

from pathlib import Path
from typing import Any

import pytest

from app.services import learning_memory as lm
from app.services.learning_memory import LearningMemory, get_lessons_for_card


@pytest.fixture
def temp_lessons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aponta o markdown de lições para um arquivo temporário isolado."""
    path = tmp_path / "agent_lessons.md"
    monkeypatch.setattr(lm, "LESSONS_PATH", path)
    return path


class _FakeCard:
    def __init__(self, *, meta: dict | None = None, column: str | None = None) -> None:
        if meta is not None:
            self.meta = meta
        if column is not None:
            self.column = column


def test_record_creates_file_and_recall_round_trip(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    mem.record_lesson("research", "Firecrawl caiu na porta 3022")

    assert temp_lessons.exists()
    lessons = mem.recall_lessons("research")
    assert "Firecrawl caiu na porta 3022" in lessons


def test_recall_returns_empty_when_file_missing(tmp_path: Path) -> None:
    mem = LearningMemory(path=tmp_path / "does_not_exist.md")
    assert mem.recall_lessons("research") == []


def test_recall_isolates_by_agent(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    mem.record_lesson("research", "SRA demora > 90s em modo cirurgia")
    mem.record_lesson("planner", "Divida o plano em fases pequenas")

    research = mem.recall_lessons("research")
    planner = mem.recall_lessons("planner")

    assert "SRA demora > 90s em modo cirurgia" in research
    assert "Divida o plano em fases pequenas" not in research
    assert "Divida o plano em fases pequenas" in planner


def test_recall_returns_last_k_in_order(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    for i in range(7):
        mem.record_lesson("dev", f"licao-{i}")

    last_three = mem.recall_lessons("dev", k=3)
    assert last_three == ["licao-4", "licao-5", "licao-6"]


def test_agent_name_is_case_insensitive(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    mem.record_lesson("Research", "Cheque o header Host localhost:3458")
    assert "Cheque o header Host localhost:3458" in mem.recall_lessons("research")


def test_multiline_lesson_is_flattened(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    mem.record_lesson("dev", "linha1\nlinha2")
    recalled = mem.recall_lessons("dev")
    assert len(recalled) == 1
    assert "\n" not in recalled[0]
    assert "linha1" in recalled[0] and "linha2" in recalled[0]


def test_lesson_with_pipe_delimiter_is_preserved(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    mem.record_lesson("research", "porta 3022 | fallback REST 3002")
    assert "porta 3022 | fallback REST 3002" in mem.recall_lessons("research")


def test_record_rejects_empty_agent_or_lesson(temp_lessons: Path) -> None:
    mem = LearningMemory(path=temp_lessons)
    with pytest.raises(ValueError):
        mem.record_lesson("", "algo")
    with pytest.raises(ValueError):
        mem.record_lesson("research", "   ")


def test_get_lessons_for_card_uses_meta_agent(temp_lessons: Path) -> None:
    LearningMemory(path=temp_lessons).record_lesson(
        "research", "Firecrawl caiu na porta 3022"
    )
    card = _FakeCard(meta={"agent": "research"})
    lessons = get_lessons_for_card(card)
    assert "Firecrawl caiu na porta 3022" in lessons


def test_get_lessons_for_card_falls_back_to_column(temp_lessons: Path) -> None:
    LearningMemory(path=temp_lessons).record_lesson(
        "planner", "Sempre leia o code_research antes de planejar"
    )
    # coluna 'planning' -> agente 'planner' (COLUMN_TO_AGENT)
    card = _FakeCard(column="planning")
    lessons = get_lessons_for_card(card)
    assert "Sempre leia o code_research antes de planejar" in lessons


def test_get_lessons_for_card_returns_empty_without_agent(temp_lessons: Path) -> None:
    card = _FakeCard()  # sem meta e sem column
    assert get_lessons_for_card(card) == []


def test_get_lessons_for_card_invalid_column_is_safe(temp_lessons: Path) -> None:
    card = _FakeCard(column="coluna-inexistente")
    assert get_lessons_for_card(card) == []


def test_no_forbidden_ecosystem_token_in_module() -> None:
    """Regra Suprema: a substring proibida não pode existir no módulo."""
    source = Path(lm.__file__).read_text(encoding="utf-8").lower()
    forbidden = "he" + "rmes"
    assert forbidden not in source
