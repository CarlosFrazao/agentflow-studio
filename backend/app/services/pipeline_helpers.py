"""Shared pipeline helpers — leitura e compressão de artifacts entre agentes.

Extraído de `app/api/v1/run.py` para ser reutilizado pelo Conductor (F-023),
que precisa dos mesmos helpers de leitura/compressão de artifacts durante a
orquestração conversacional. Mantém a lógica idêntica; apenas centraliza.
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.artifact import Artifact
from app.models.budget import BudgetLimit
from app.models.card import Card
from app.models.project import Project
from app.services.artifact_compressor import compress_artifact
from app.services.orchestrator import should_compress_artifact

logger = get_logger("pipeline_helpers")


async def latest_artifact_content(
    session: AsyncSession, card_id, agent_name: str
) -> str | None:
    """Retorna o conteúdo do artifact mais recente de um agente para o card.

    Ordena por `created_at DESC, id DESC` — o id é uuid4 (não ordenável no
    tempo), então `created_at` é a chave primária, com o id como desempate
    estável. Evita pegar um artifact mais antigo quando os UUIDs não são
    cronologicamente ordenáveis (mesmo bug corrigido em _recent_messages).
    """
    stmt = (
        select(Artifact.content)
        .where(Artifact.card_id == card_id, Artifact.agent_name == agent_name)
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def parse_ideation(content: str | None) -> dict:
    """Parseia o conteúdo do artifact Ideation (model_dump_json de IdeationOutput).

    Fail-open: se ausente ou inválido, devolve dict vazio (o Planner tolera
    ideation={}). Nunca quebramos o pipeline por JSON malformado aqui.
    """
    if not content:
        return {}
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        logger.warning("ideation_artifact_parse_failed", preview=content[:120])
        return {}
    return data if isinstance(data, dict) else {}


async def budget_remaining_usd(session: AsyncSession, card: Card) -> float | None:
    """Orçamento restante do dono do card (F-011), ou None se sem limite.

    Percorre card -> project -> user -> BudgetLimit. Retorna a folga mensal
    (`monthly_limit - current_spend`). None quando não há projeto com dono ou
    quando não existe BudgetLimit configurado (MVP single-tenant sem cap).
    """
    project = await session.get(Project, card.project_id)
    if project is None or project.user_id is None:
        return None
    stmt = select(BudgetLimit).where(BudgetLimit.user_id == project.user_id)
    budget = (await session.execute(stmt)).scalar_one_or_none()
    if budget is None:
        return None
    return budget.monthly_limit_usd - budget.current_month_spend_usd


async def maybe_compress(text: str, budget_remaining_usd: float | None) -> str:
    """Comprime um artefato grande antes do handoff, respeitando o budget (F-011).

    Fail-open: qualquer falha na compressão devolve o texto original — a
    compressão é complementar e nunca pode derrubar o pipeline.
    """
    if not text:
        return text
    settings = get_settings()
    if not settings.compression_enabled:
        return text
    if not should_compress_artifact(
        text,
        threshold_chars=settings.compression_threshold_chars,
        budget_remaining_usd=budget_remaining_usd,
    ):
        return text
    try:
        compressed = await compress_artifact(
            text, budget_tokens=settings.compression_budget_tokens
        )
        logger.debug(
            "artifact_handoff_compressed",
            original_chars=len(text),
            compressed_chars=len(compressed),
        )
        return compressed
    except Exception as exc:  # noqa: BLE001
        logger.warning("artifact_handoff_compression_failed", error=str(exc))
        return text
