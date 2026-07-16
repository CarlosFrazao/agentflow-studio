"""Testes TDD do orquestrador (máquina de estados do pipeline Kanban).

Cobertura: mapeamento coluna→agente, transição válida, auto-approve (ADR-007),
e que a próxima coluna respeita o fluxo do PRD F-001.
"""

import pytest
from typing import Any

from app.services.orchestrator import (
    PIPELINE_ORDER,
    column_after_review,
    handle_review_cycle,
    inject_context,
    next_agent_for_column,
    next_column,
    resume_from_column,
    should_auto_approve,
)


class _FakeCard:
    """Card mínimo para exercitar handle_review_cycle / inject_context."""

    def __init__(self, card_id: str | None = None, title: str | None = None) -> None:
        self.id = card_id
        self.title = title


def test_pipeline_order_follows_prd_columns() -> None:
    assert list(PIPELINE_ORDER) == [
        "backlog",
        "researching",
        "planning",
        "reviewing",
        "production",
        "done",
    ]


@pytest.mark.parametrize(
    "column,expected_agent",
    [
        ("backlog", "ideation"),
        ("researching", "research"),
        ("planning", "planner"),
        ("reviewing", "reviewer"),
        ("production", "dev"),
        ("done", None),
    ],
)
def test_next_agent_for_column(column: str, expected_agent: str | None) -> None:
    assert next_agent_for_column(column) == expected_agent


@pytest.mark.parametrize(
    "column,expected_next",
    [
        ("backlog", "researching"),
        ("researching", "planning"),
        ("planning", "reviewing"),
        ("reviewing", "production"),
        ("production", "done"),
        ("done", "done"),
    ],
)
def test_next_column_advances_pipeline(column: str, expected_next: str) -> None:
    assert next_column(column) == expected_next


def test_should_auto_approve_when_high_confidence_and_no_critical() -> None:
    assert should_auto_approve(confidence_score=0.90, critical_alerts=0) is True


def test_should_not_auto_approve_below_threshold() -> None:
    assert should_auto_approve(confidence_score=0.84, critical_alerts=0) is False


def test_should_not_auto_approve_with_critical_alert() -> None:
    assert should_auto_approve(confidence_score=0.95, critical_alerts=1) is False


def test_should_not_auto_approve_at_exact_threshold() -> None:
    # PRD F-007: >= 0.85 (inclusivo)
    assert should_auto_approve(confidence_score=0.85, critical_alerts=0) is True


# ── Fase B2: retomada, ciclo de revisão e injeção de contexto ──────────────


@pytest.mark.parametrize(
    "column,expected_agent",
    [
        ("backlog", "ideation"),
        ("researching", "research"),
        ("planning", "planner"),
        ("reviewing", "reviewer"),
        ("production", "dev"),
        ("done", None),
    ],
)
def test_resume_from_column_maps_to_agent(column: str, expected_agent: str | None) -> None:
    assert resume_from_column(column) == expected_agent


def test_resume_from_column_invalid_column_raises() -> None:
    with pytest.raises(ValueError, match="coluna invalida para retomada"):
        resume_from_column("flying")


def test_resume_from_column_terminal_done_returns_none() -> None:
    # Coluna terminal 'done' não tem agente associado (retoma para None).
    assert resume_from_column("done") is None


def test_resume_from_column_all_columns_resolve() -> None:
    # Toda coluna do pipeline deve resolver para um agente (ou None em 'done').
    for column in PIPELINE_ORDER[:-1]:
        assert resume_from_column(column) is not None
    assert resume_from_column("done") is None


def test_handle_review_cycle_rejected_returns_production() -> None:
    card = _FakeCard(card_id="card-1", title="Site X")
    result = handle_review_cycle(
        card=card,
        review_passed=False,
        confidence=0.95,
        critical_alerts=0,
    )
    assert result == "production"


def test_handle_review_cycle_approved_low_confidence_stays_reviewing() -> None:
    card = _FakeCard(card_id="card-2", title="Site Y")
    result = handle_review_cycle(
        card=card,
        review_passed=True,
        confidence=0.80,
        critical_alerts=0,
    )
    assert result == "reviewing"


def test_handle_review_cycle_approved_high_confidence_done() -> None:
    card = _FakeCard(card_id="card-3", title="Site Z")
    result = handle_review_cycle(
        card=card,
        review_passed=True,
        confidence=0.95,
        critical_alerts=0,
    )
    assert result == "done"


def test_handle_review_cycle_critical_alert_blocks_done() -> None:
    card = _FakeCard(card_id="card-4", title="Site W")
    result = handle_review_cycle(
        card=card,
        review_passed=True,
        confidence=0.95,
        critical_alerts=2,
    )
    assert result == "reviewing"


def test_handle_review_cycle_equivalence_with_column_after_review() -> None:
    # handle_review_cycle deve ser um wrapper fiel sobre column_after_review.
    card = _FakeCard(title="eq")
    scenarios = [
        (False, 0.90, 0, "production"),
        (True, 0.90, 0, "done"),
        (True, 0.70, 0, "reviewing"),
        (True, 0.90, 1, "reviewing"),
    ]
    for passed, conf, alerts, expected in scenarios:
        assert handle_review_cycle(card, passed, conf, alerts) == expected
        assert column_after_review(conf, alerts, passed) == expected


def test_inject_context_without_d_modules_returns_base_prompt() -> None:
    # Fases D1/D2 ainda não existem no disco -> fallback silencioso.
    card = _FakeCard(card_id="card-9")
    prompt = "Gere o código do card."
    assert inject_context(card, prompt) == prompt


def test_inject_context_uses_learning_memory_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    card = _FakeCard(card_id="card-10")

    def fake_get_lessons(c: Any) -> list[str]:
        assert c is card
        return ["Evite hardcoded secrets", "Prefira async para I/O"]

    # Simula a existência do módulo D2 (import real falharia pois não existe).
    fake_module = type("M", (), {"get_lessons_for_card": staticmethod(fake_get_lessons)})()
    monkeypatch.setitem(sys.modules, "app.services.learning_memory", fake_module)
    try:
        result = inject_context(card, "Base prompt.")
    finally:
        monkeypatch.undo()

    assert "Base prompt." in result
    assert "Evite hardcoded secrets" in result
    assert "Prefira async para I/O" in result


def test_inject_context_uses_preference_graph_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    card = _FakeCard(card_id="card-11")

    def fake_get_prefs(c: Any) -> list[str]:
        return ["Use tema escuro por padrão"]

    fake_module = type("M", (), {"get_preferences_for_card": staticmethod(fake_get_prefs)})()
    monkeypatch.setitem(sys.modules, "app.services.preference_graph", fake_module)
    try:
        result = inject_context(card, "Base prompt.")
    finally:
        monkeypatch.undo()

    assert "Base prompt." in result
    assert "Use tema escuro por padrão" in result


def test_inject_context_combines_lessons_and_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    card = _FakeCard(card_id="card-12")

    def fake_get_lessons(c: Any) -> list[str]:
        return ["Evite hardcoded secrets"]

    def fake_get_prefs(c: Any) -> list[str]:
        return ["Use tema escuro por padrão"]

    lessons_mod = type("M", (), {"get_lessons_for_card": staticmethod(fake_get_lessons)})()
    prefs_mod = type("M", (), {"get_preferences_for_card": staticmethod(fake_get_prefs)})()
    monkeypatch.setitem(sys.modules, "app.services.learning_memory", lessons_mod)
    monkeypatch.setitem(sys.modules, "app.services.preference_graph", prefs_mod)
    try:
        result = inject_context(card, "Base prompt.")
    finally:
        monkeypatch.undo()

    # Ambos os blocos devem estar presentes e o prompt base preservado.
    assert "Base prompt." in result
    assert "Lições aprendidas" in result
    assert "Evite hardcoded secrets" in result
    assert "Preferências do usuário" in result
    assert "Use tema escuro por padrão" in result
    # Lições aparecem antes das preferências na ordem de concatenação.
    assert result.index("Lições aprendidas") < result.index("Preferências do usuário")


def test_inject_context_empty_lessons_does_not_add_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    card = _FakeCard(card_id="card-13")

    def fake_get_lessons(c: Any) -> list[str]:
        return []

    lessons_mod = type("M", (), {"get_lessons_for_card": staticmethod(fake_get_lessons)})()
    monkeypatch.setitem(sys.modules, "app.services.learning_memory", lessons_mod)
    try:
        result = inject_context(card, "Base prompt.")
    finally:
        monkeypatch.undo()

    # Módulo D2 disponível mas vazio -> sem bloco de lições, prompt base intacto.
    assert result == "Base prompt."


def test_inject_context_with_real_learning_memory(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integração real (sem mock): inject_context consome learning_memory (D2).

    Grava uma lição de verdade num markdown temporário e verifica que ela é
    injetada no prompt via o módulo real ``app.services.learning_memory``.
    """
    from app.services import learning_memory as real_lm
    from app.services.learning_memory import LearningMemory

    lessons_file = tmp_path / "agent_lessons.md"
    monkeypatch.setattr(real_lm, "LESSONS_PATH", lessons_file)

    LearningMemory().record_lesson("research", "Firecrawl caiu na porta 3022")

    class _CardWithColumn:
        id = "card-real"
        title = "Pesquisa"
        column = "researching"  # -> agente 'research'
        meta = {"agent": "research"}

    result = inject_context(_CardWithColumn(), "Base prompt.")
    assert "Base prompt." in result
    assert "Firecrawl caiu na porta 3022" in result
    assert "Lições aprendidas" in result


# ---------------------------------------------------------------------------
# FEAT-009: revert_auto_approval — desfazer auto-approve dentro da janela (R4)
# ---------------------------------------------------------------------------


class _RevertCard:
    """Card mutável mínimo para exercitar revert_auto_approval (helper puro)."""

    def __init__(
        self,
        *,
        column: str,
        auto_approved: bool = False,
        approval_by: str = "none",
        revert_deadline=None,
    ) -> None:
        self.column = column
        self.auto_approved = auto_approved
        self.approval_by = approval_by
        self.revert_deadline = revert_deadline


def test_prev_column_returns_previous_in_pipeline() -> None:
    from app.services.orchestrator import prev_column

    assert prev_column("done") == "production"
    assert prev_column("production") == "reviewing"
    assert prev_column("researching") == "backlog"
    # backlog é o início: não há coluna anterior.
    assert prev_column("backlog") == "backlog"


def test_prev_column_rejects_invalid_column() -> None:
    from app.services.orchestrator import prev_column

    with pytest.raises(ValueError):
        prev_column("coluna-inexistente")


def test_revert_within_window_reverts_column_and_clears_flags() -> None:
    from datetime import datetime, timedelta, timezone

    from app.services.orchestrator import revert_auto_approval

    future = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
    card = _RevertCard(
        column="done",
        auto_approved=True,
        approval_by="auto",
        revert_deadline=future,
    )
    ok = revert_auto_approval(card)
    assert ok is True
    assert card.column == "production"  # done -> production
    assert card.auto_approved is False
    assert card.approval_by == "none"
    assert card.revert_deadline is None


def test_revert_outside_window_returns_false_and_keeps_state() -> None:
    from datetime import datetime, timedelta, timezone

    from app.services.orchestrator import revert_auto_approval

    past = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
    card = _RevertCard(
        column="done",
        auto_approved=True,
        approval_by="auto",
        revert_deadline=past,
    )
    ok = revert_auto_approval(card)
    assert ok is False
    # Estado preservado: nada é revertido fora da janela.
    assert card.column == "done"
    assert card.auto_approved is True
    assert card.approval_by == "auto"


def test_revert_when_not_auto_approved_returns_false() -> None:
    from app.services.orchestrator import revert_auto_approval

    card = _RevertCard(column="reviewing", auto_approved=False)
    ok = revert_auto_approval(card)
    assert ok is False
    assert card.column == "reviewing"


def test_revert_at_backlog_does_not_break() -> None:
    from datetime import datetime, timedelta, timezone

    from app.services.orchestrator import revert_auto_approval

    future = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
    card = _RevertCard(
        column="backlog",
        auto_approved=True,
        approval_by="auto",
        revert_deadline=future,
    )
    ok = revert_auto_approval(card)
    assert ok is True
    # backlog não tem coluna anterior: permanece em backlog, mas limpa flags.
    assert card.column == "backlog"
    assert card.auto_approved is False
    assert card.approval_by == "none"
    assert card.revert_deadline is None
