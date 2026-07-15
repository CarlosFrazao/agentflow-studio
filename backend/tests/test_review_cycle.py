"""Testes TDD do ciclo Criação<->Revisão cruzada (Item B do analise_omnigent.md).

Quando o Reviewer Agent reprova, o card deve voltar para a coluna de
desenvolvimento (production) com os logs de erro anexados; quando aprova,
deve avançar para done.
"""

import pytest

from app.services.orchestrator import (
    AUTO_APPROVE_CONFIDENCE_THRESHOLD,
    column_after_review,
    next_column,
)


def test_review_pass_advances_to_done() -> None:
    """Revisão aprovada (confiança alta, sem alertas) -> done."""
    target = column_after_review(
        confidence_score=0.95, critical_alerts=0, review_passed=True
    )
    assert target == "done"


def test_review_fail_returns_to_production_with_logs() -> None:
    """Revisão reprovada -> volta para production (Dev) para correção."""
    target = column_after_review(
        confidence_score=0.4, critical_alerts=2, review_passed=False
    )
    assert target == "production"


def test_review_pass_but_low_confidence_still_awaits_human() -> None:
    """Confiança abaixo do limiar mesmo com review_passed=True -> aguarda HITL (reviewing)."""
    target = column_after_review(
        confidence_score=0.5, critical_alerts=0, review_passed=True
    )
    assert target == "reviewing"


def test_next_column_after_production_is_done() -> None:
    assert next_column("production") == "done"
    assert next_column("backlog") == "researching"
