"""Compressão de artefatos entre agentes (Fase B1).

O relatório do SRA (Markdown de ~8 seções) e o output do Code Research podem
ser grandes e encarecer o contexto dos agentes seguintes (Planner/Reviewer).
Este módulo comprime esses artefatos antes do handoff:

1. `prune_tool_output` — pré-passe barato, SEM LLM: protege head/tail e corta
   o miolo verboso de saídas grandes (evita gastar o modelo com ruído).
2. `compress_artifact` — resume relatórios grandes via modelo auxiliar barato
   (`call_aux_llm`), preservando seções-chave ("concorrentes" e "gaps").

Adaptado da lógica de um compressor de contexto de referência: protege
head/tail, orçamento de resumo proporcional ao conteúdo, template estruturado
e fail-open (nunca derruba o pipeline se o LLM auxiliar falhar).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.services.llm import LLMError, call_aux_llm

logger = get_logger("artifact_compressor")

# Só comprime artefatos acima deste tamanho (chars).
COMPRESS_THRESHOLD_CHARS = 4000

# Parâmetros do pré-passe de prune (protege head/tail, corta o miolo).
_PRUNE_TRIGGER_CHARS = 2000
_PRUNE_HEAD_CHARS = 1200
_PRUNE_TAIL_CHARS = 600
_PRUNE_MARKER = "\n...[conteúdo intermediário truncado para poupar contexto]...\n"

# Orçamento de resumo: proporcional ao conteúdo, com piso e teto (chars ≈ token*4).
_CHARS_PER_TOKEN = 4
_SUMMARY_RATIO = 0.20
_MIN_SUMMARY_TOKENS = 200
_SUMMARY_TOKENS_CEILING = 2000

# Seções que NUNCA podem sumir do resumo (critério de aceitação da Fase B1).
_KEY_SECTIONS = ("concorrentes", "gaps")


def prune_tool_output(text: str) -> str:
    """Pré-passe barato (sem LLM): corta saída verbose antes do LLM resumir.

    Preserva o início (`_PRUNE_HEAD_CHARS`) e o fim (`_PRUNE_TAIL_CHARS`) do
    texto — onde normalmente ficam a intenção e as conclusões — e substitui o
    miolo por um marcador curto. Textos abaixo de `_PRUNE_TRIGGER_CHARS` são
    devolvidos intactos.
    """
    if not text or len(text) <= _PRUNE_TRIGGER_CHARS:
        return text

    head = text[:_PRUNE_HEAD_CHARS]
    tail = text[-_PRUNE_TAIL_CHARS:]
    return f"{head}{_PRUNE_MARKER}{tail}"


def _compute_summary_budget(text: str, budget_tokens: int) -> int:
    """Escala o orçamento do resumo com o tamanho do conteúdo (piso/teto)."""
    content_tokens = max(1, len(text) // _CHARS_PER_TOKEN)
    scaled = int(content_tokens * _SUMMARY_RATIO)
    ceiling = min(budget_tokens, _SUMMARY_TOKENS_CEILING)
    return max(_MIN_SUMMARY_TOKENS, min(scaled, ceiling))


def _build_prompts(text: str, summary_budget: int) -> tuple[str, str]:
    """Monta (system_prompt, user_prompt) para o resumo estruturado."""
    system_prompt = (
        "Você é um agente de compressão de contexto. Resuma o relatório abaixo "
        "de forma fiel e concisa, em Markdown, na MESMA língua do original. "
        "PRESERVE OBRIGATORIAMENTE, sem omitir, as seções de 'Concorrentes' e "
        "'Gaps' (lacunas de mercado) — elas são críticas para as etapas "
        "seguintes. Mantenha títulos de seção como cabeçalhos Markdown. "
        "Descarte detalhes redundantes e texto de preenchimento. "
        "Não invente informação e não adicione preâmbulo — devolva apenas o "
        f"resumo estruturado. Alvo aproximado: {summary_budget} tokens."
    )
    user_prompt = (
        "RELATÓRIO A RESUMIR (preserve 'Concorrentes' e 'Gaps'):\n\n"
        f"{text}"
    )
    return system_prompt, user_prompt


def _has_key_sections(text: str) -> bool:
    lowered = text.lower()
    return all(section in lowered for section in _KEY_SECTIONS)


async def compress_artifact(text: str, budget_tokens: int = 800) -> str:
    """Resume relatórios grandes (ex: SRA) preservando seções-chave.

    Regras:
    - Só comprime se `len(text) > COMPRESS_THRESHOLD_CHARS`; senão devolve intacto.
    - Aplica `prune_tool_output` antes de chamar o LLM (reduz custo do resumo).
    - Usa `call_aux_llm` (modelo barato), não o modelo principal.
    - Fail-open: se o LLM auxiliar falhar, devolve a versão prunada do original
      (nunca levanta exceção — compressão é complementar ao pipeline).
    - Se o resumo do LLM perder as seções-chave, descarta-o e mantém o prunado.
    """
    if not text or len(text) <= COMPRESS_THRESHOLD_CHARS:
        return text

    pruned = prune_tool_output(text)
    summary_budget = _compute_summary_budget(text, budget_tokens)
    system_prompt, user_prompt = _build_prompts(text, summary_budget)

    try:
        summary = await call_aux_llm(system_prompt, user_prompt)
    except LLMError as exc:
        logger.warning(
            "artifact_compression_llm_failed",
            error=str(exc),
            original_chars=len(text),
        )
        return pruned

    summary = (summary or "").strip()
    if not summary:
        logger.warning("artifact_compression_empty_summary", original_chars=len(text))
        return pruned

    # Guarda de qualidade: se o original tinha as seções-chave e o resumo as
    # perdeu, o resumo é inaceitável — degrada para o texto prunado, que ao
    # menos preserva head/tail do conteúdo real.
    if _has_key_sections(text) and not _has_key_sections(summary):
        logger.warning(
            "artifact_compression_dropped_key_sections",
            original_chars=len(text),
            summary_chars=len(summary),
        )
        return pruned

    logger.info(
        "artifact_compressed",
        original_chars=len(text),
        summary_chars=len(summary),
        ratio=round(len(summary) / len(text), 3),
    )
    return summary
