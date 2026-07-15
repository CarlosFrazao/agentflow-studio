"""Orquestrador — máquina de estados do pipeline Kanban (padrão Supervisor).

Responsabilidades (isoladas, testáveis):
- Mapear coluna -> agente especialista (PRD F-001/F-002..F-006).
- Calcular próxima coluna no fluxo linear.
- Decidir auto-approve (ADR-007: confidence >= 0.85 E zero alertas críticos).

A execução de I/O (LLM, MCP) fica nos agents/services; este módulo é puro.
"""

import logging
from typing import Any

from app.models.card import KANBAN_COLUMNS

logger = logging.getLogger(__name__)

# Fluxo linear do pipeline (PRD F-001)
PIPELINE_ORDER: tuple[str, ...] = (
    "backlog",
    "researching",
    "planning",
    "reviewing",
    "production",
    "done",
)

# Coluna -> agente especialista que roda nela
COLUMN_TO_AGENT: dict[str, str | None] = {
    "backlog": "ideation",
    "researching": "research",
    "planning": "planner",
    "reviewing": "reviewer",
    "production": "dev",
    "done": None,
}

# Limiar de auto-approve (ADR-007)
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.85


def next_agent_for_column(column: str) -> str | None:
    if column not in COLUMN_TO_AGENT:
        raise ValueError(f"coluna invalida: {column}")
    return COLUMN_TO_AGENT[column]


def next_column(column: str) -> str:
    if column not in PIPELINE_ORDER:
        raise ValueError(f"coluna invalida: {column}")
    idx = PIPELINE_ORDER.index(column)
    if idx >= len(PIPELINE_ORDER) - 1:
        return "done"
    return PIPELINE_ORDER[idx + 1]


def should_auto_approve(confidence_score: float, critical_alerts: int) -> bool:
    return (
        confidence_score >= AUTO_APPROVE_CONFIDENCE_THRESHOLD
        and critical_alerts <= 0
    )


def should_compress_artifact(
    text: str,
    *,
    threshold_chars: int,
    budget_remaining_usd: float | None,
) -> bool:
    """Decide se um artefato deve ser comprimido antes do handoff (Fase B1).

    Função pura (sem I/O), respeita o cap de orçamento (F-011):
    - Só comprime textos acima de `threshold_chars`.
    - Se `budget_remaining_usd` <= 0, NÃO comprime (evita gastar LLM auxiliar
      após o cap ser atingido). `None` = sem limite conhecido (permite).
    """
    if not text or len(text) <= threshold_chars:
        return False
    if budget_remaining_usd is not None and budget_remaining_usd <= 0:
        return False
    return True


def column_after_review(
    confidence_score: float, critical_alerts: int, review_passed: bool
) -> str:
    """Roteia o card após a etapa de revisão (ciclo Criação<->Revisão, Item B).

    - Reprovado (review_passed=False): volta para 'production' (Dev) para
      correção, com logs de erro anexados pelo chamador.
    - Aprovado mas confiança abaixo do limiar ADR-007: permanece em 'reviewing'
      aguardando aprovação humana (HITL) — não avança sozinho.
    - Aprovado com confiança suficiente: avança para 'done'.
    """
    if not review_passed:
        return "production"
    if confidence_score < AUTO_APPROVE_CONFIDENCE_THRESHOLD or critical_alerts > 0:
        return "reviewing"
    return "done"


def resume_from_column(column: str) -> str | None:
    """Recalcula o agente correto ao retomar um card após restart do backend.

    Inspeciona a coluna persistida no banco (estado de sobrevivência) e a
    mapeia de volta para o agente especialista que deve processá-la. Levanta
    ValueError se a coluna não fizer parte do pipeline (estado corrompido).

    Retorna None apenas para a coluna terminal 'done' (sem agente associado).
    """
    if column not in COLUMN_TO_AGENT:
        raise ValueError(f"coluna invalida para retomada: {column}")
    agent = COLUMN_TO_AGENT[column]
    logger.info(
        "retomada de card: coluna=%s -> agente=%s",
        column,
        agent if agent is not None else "terminal",
    )
    return agent


def handle_review_cycle(
    card: Any,
    review_passed: bool,
    confidence: float,
    critical_alerts: int,
) -> str:
    """Wrapper sobre column_after_review com logging estruturado do ciclo.

    Registra o desfecho do ciclo Criação<->Revisão (Item B do PRD) e retorna a
    coluna de destino. O card só é mutado pelo chamador (I/O); aqui apenas
    decidimos e registramos.
    """
    target = column_after_review(confidence, critical_alerts, review_passed)
    card_id = getattr(card, "id", None)
    card_title = getattr(card, "title", None)
    logger.info(
        "ciclo revisao concluido: card_id=%s title=%r review_passed=%s "
        "confidence=%.3f critical_alerts=%d -> coluna=%s",
        card_id,
        card_title,
        review_passed,
        confidence,
        critical_alerts,
        target,
    )
    return target


def inject_context(card: Any, base_prompt: str) -> str:
    """Injeta lições aprendidas (Fase D2) + preferências (Fase D1) no prompt.

    Lê lições de ``app.services.learning_memory`` e preferências de
    ``app.services.preference_graph`` e concatena ao prompt somente se houver
    conteúdo. Fallback silencioso (sem quebrar a pipeline) caso os módulos
    das Fases D1/D2 ainda não existam no disco — desacopla a ordem das fases.
    """
    segments: list[str] = []

    # Fase D2 — learning_memory (lições incrementais)
    try:
        from app.services.learning_memory import get_lessons_for_card

        lessons = get_lessons_for_card(card)
        if lessons:
            joined = "\n".join(f"- {line}" for line in lessons)
            segments.append(
                "Lições aprendidas de ciclos anteriores (apply antes de gerar):\n"
                f"{joined}"
            )
    except ImportError as exc:
        logger.debug(
            "inject_context: learning_memory indisponível (Fase D2), pulando lições: %s",
            exc,
        )

    # Fase D1 — preference_graph (preferências do usuário)
    try:
        from app.services.preference_graph import get_preferences_for_card

        preferences = get_preferences_for_card(card)
        if preferences:
            joined = "\n".join(f"- {line}" for line in preferences)
            segments.append(
                "Preferências do usuário (honre neste card):\n"
                f"{joined}"
            )
    except ImportError as exc:
        logger.debug(
            "inject_context: preference_graph indisponível (Fase D1), pulando preferências: %s",
            exc,
        )

    if not segments:
        return base_prompt

    context_block = "\n\n".join(segments)
    logger.info(
        "inject_context: %d bloco(s) de contexto adicionado(s) ao prompt",
        len(segments),
    )
    return f"{base_prompt}\n\n{context_block}"
