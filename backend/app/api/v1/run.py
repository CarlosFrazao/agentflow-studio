"""Endpoint /run — orquestrador (máquina de estados) exposto via API.

Executa o agente especialista da coluna atual do card, persiste o Artifact e
a Execution, avança o card para a próxima coluna e aplica auto-approve (ADR-007)
quando confidence >= 0.85 e sem alertas críticos do Reviewer.
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_request_id
from app.services.deps import get_firecrawl, get_github, get_llm, get_sra
from app.core.database import get_session
from app.core.config import get_settings
from sqlalchemy import select
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.responses import success_envelope
from app.models.artifact import Artifact
from app.models.budget import BudgetLimit
from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project
from app.services.agents.code_research import CodeResearchAgent
from app.services.agents.dev import DevAgent
from app.services.agents.ideation import IdeationAgent
from app.services.agents.planner import PlannerAgent
from app.services.agents.research import ResearchAgent
from app.services.agents.reviewer import ReviewerAgent
from app.services.artifact_compressor import compress_artifact
from app.services.orchestrator import (
    next_agent_for_column,
    next_column,
    should_auto_approve,
    should_compress_artifact,
    column_after_review,
)

router = APIRouter(prefix="/cards", tags=["run"])
logger = get_logger("run_endpoint")


async def _latest_artifact_content(session, card_id, agent_name: str) -> str | None:
    """Retorna o conteúdo do artifact mais recente de um agente para o card."""
    stmt = (
        select(Artifact.content)
        .where(Artifact.card_id == card_id, Artifact.agent_name == agent_name)
        .order_by(Artifact.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _budget_remaining_usd(session, card) -> float | None:
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


async def _maybe_compress(text: str, budget_remaining_usd: float | None) -> str:
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

AUTO_APPROVE_REVERT_WINDOW_MIN = 30


@router.post("/{card_id}/run", response_model=None)
async def run_card(
    card_id: UUID,
    request: Request,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
    llm=Depends(get_llm),
    sra=Depends(get_sra),
    firecrawl=Depends(get_firecrawl),
    github=Depends(get_github),
) -> dict:
    card = await session.get(Card, card_id)
    if not card:
        raise NotFoundError("Card", str(card_id))

    agent_name = next_agent_for_column(card.column)
    if agent_name is None:
        return success_envelope(
            data={"status": "done", "column": card.column}, request_id=request_id
        )

    settings = get_settings()
    # DEMO_MODE é opt-in explícito (env DEMO_MODE=true). Não dispara só por
    # ausência de chave — isso silenciosamente desligaria os agentes reais em
    # qualquer ambiente sem GEMINI_API_KEY (incl. a suíte de testes).
    if settings.demo_mode:
        return await _run_demo(card, agent_name, request_id, session)

    execution = Execution(card_id=card.id, agent_name=agent_name, status="running")
    session.add(execution)
    await session.commit()

    started = datetime.now(tz=timezone.utc)
    try:
        dispatch_result = await _dispatch(
            agent_name, card, llm, sra, firecrawl, github, session
        )
        artifact_content = dispatch_result["content"]
        confidence = dispatch_result["confidence"]
        critical_alerts = dispatch_result["critical_alerts"]
        extra_artifacts = dispatch_result.get("extra_artifacts", [])
    except Exception as exc:
        finished = datetime.now(tz=timezone.utc)
        execution.status = "failed"
        execution.error_message = str(exc)
        execution.finished_at = finished
        execution.duration_ms = int((finished - started).total_seconds() * 1000)
        await session.commit()
        logger.error("agent_failed", agent=agent_name, error=str(exc))
        return success_envelope(
            data={"status": "failed", "agent": agent_name, "error": str(exc)},
            request_id=request_id,
        )

    finished = datetime.now(tz=timezone.utc)
    execution.status = "success"
    execution.finished_at = finished
    execution.duration_ms = int((finished - started).total_seconds() * 1000)
    await session.commit()

    # persiste artifact principal
    artifact = Artifact(
        card_id=card.id, agent_name=agent_name, type="json", content=artifact_content
    )
    session.add(artifact)

    # persiste artifacts auxiliares (ex: code_research da etapa de research)
    for extra in extra_artifacts:
        session.add(
            Artifact(
                card_id=card.id,
                agent_name=extra["agent_name"],
                type="json",
                content=extra["content"],
            )
        )

    # avança coluna: agentes normais usam next_column (linear); o reviewer
    # devolve target_column explícito (roteamento pós-revisão, Item B).
    target_column = dispatch_result.get("target_column")
    if target_column is not None:
        card.column = target_column
    else:
        card.column = next_column(card.column)

    card.confidence_score = confidence

    # Reviewer reprovado: anexa logs de erro ao meta do card.
    review_logs = dispatch_result.get("review_logs")
    if review_logs is not None:
        meta = dict(card.meta or {})
        meta["review_logs"] = review_logs
        card.meta = meta

    if should_auto_approve(confidence, critical_alerts):
        card.approval_by = "auto"
        card.auto_approved = True
        card.revert_deadline = finished + timedelta(
            minutes=AUTO_APPROVE_REVERT_WINDOW_MIN
        )
    await session.commit()
    await session.refresh(card)

    return success_envelope(
        data={
            "status": "success",
            "agent": agent_name,
            "column": card.column,
            "auto_approved": card.auto_approved,
            "execution_id": str(execution.id),
        },
        request_id=request_id,
    )


async def _run_demo(card, agent_name, request_id, session) -> dict:
    """Modo demo: avança o card sem chamar LLM real (economiza custo/erros).

    Persiste uma Execution (status success, sem custo) e avança a coluna,
    mantendo o comportamento do board consistente com o fluxo real.
    """
    execution = Execution(
        card_id=card.id, agent_name=agent_name, status="success", cost_usd=0.0
    )
    session.add(execution)
    await session.commit()

    card.column = next_column(card.column)
    card.confidence_score = 0.0
    await session.commit()
    await session.refresh(card)

    logger.info("demo_run", agent=agent_name, card=str(card.id))
    return success_envelope(
        data={
            "status": "success",
            "agent": agent_name,
            "column": card.column,
            "auto_approved": card.auto_approved,
            "execution_id": str(execution.id),
            "demo": True,
        },
        request_id=request_id,
    )


async def _dispatch(agent_name, card, llm, sra, firecrawl, github, session):
    """Roteia para o agente correto e retorna um dict:

    {
        "content": str,            # artifact principal do agente da coluna
        "confidence": float,
        "critical_alerts": int,
        "extra_artifacts": list,   # artifacts auxiliares (ex: code_research)
    }
    """
    if agent_name == "ideation":
        out = await IdeationAgent(llm=llm).run(card.title)
        return {
            "content": out.model_dump_json(),
            "confidence": out.confidence_score,
            "critical_alerts": 0,
        }
    if agent_name == "research":
        # Research (SRA) + Code Research (GitHub + Firecrawl) rodam juntos.
        out = await ResearchAgent(llm=llm, sra=sra).run(card.title)
        result: dict = {
            "content": out.model_dump_json(),
            "confidence": out.confidence,
            "critical_alerts": 0,
            "extra_artifacts": [],
        }
        try:
            logger.debug(
                "code_research_calling",
                card=str(card.id),
                query=card.title,
            )
            code_out = await CodeResearchAgent(llm=llm, github=github, firecrawl=firecrawl).run(
                query=card.title, per_page=3
            )
            logger.debug(
                "code_research_done",
                card=str(card.id),
                suggestions=len(code_out.suggestions),
                license_class=code_out.license_class,
                degraded=code_out.degraded,
            )
            if code_out.suggestions or code_out.license_class != "unknown":
                result["extra_artifacts"].append(
                    {"agent_name": "code_research", "content": code_out.model_dump_json()}
                )
        except Exception as exc:
            # Code Research é complementar: nunca derruba o Research.
            logger.warning("code_research_skipped", error=str(exc))
        return result
    if agent_name == "planner":
        # Transição researching -> planning (Fase B1): o relatório do SRA
        # (research) e o output do Code Research podem ser grandes; comprime-os
        # com o modelo auxiliar barato antes do handoff, respeitando o cap de
        # orçamento (F-011).
        budget_remaining = await _budget_remaining_usd(session, card)
        research_content = await _latest_artifact_content(session, card.id, "research")
        cr_content = await _latest_artifact_content(session, card.id, "code_research")
        research_compressed = await _maybe_compress(
            research_content or "", budget_remaining
        )
        cr_compressed = await _maybe_compress(cr_content or "", budget_remaining)
        logger.debug(
            "planner_consuming_artifacts",
            card=str(card.id),
            has_research=bool(research_content),
            has_code_research=bool(cr_content),
            research_size=len(research_content or ""),
            research_compressed_size=len(research_compressed),
            code_research_size=len(cr_content or ""),
            code_research_compressed_size=len(cr_compressed),
            budget_remaining=budget_remaining,
        )
        out = await PlannerAgent(llm=llm).run(
            ideation={}, research=research_compressed, code_research=cr_compressed
        )
        return {
            "content": out.model_dump_json(),
            "confidence": 0.0,
            "critical_alerts": 0,
        }
    if agent_name == "reviewer":
        out = await ReviewerAgent(llm=llm).run(
            ideation={}, research="", planner="", code_research=""
        )
        # Roteamento pós-revisão (Item B / ADR-007): reprovado -> production,
        # aprovado c/ confiança baixa -> reviewing (HITL), aprovado alto -> done.
        target_col = column_after_review(
            confidence_score=out.confidence_score,
            critical_alerts=out.critical_count,
            review_passed=out.passed,
        )
        logger.debug(
            "reviewer_routing",
            card=str(card.id),
            passed=out.passed,
            confidence=out.confidence_score,
            critical=out.critical_count,
            target_col=target_col,
        )
        return {
            "content": out.model_dump_json(),
            "confidence": out.confidence_score,
            "critical_alerts": out.critical_count,
            # Sinaliza ao run_card para usar este destino em vez de next_column.
            "target_column": target_col,
            # Anexado ao meta do card quando volta para production (reprovado).
            "review_logs": out.log_summary if target_col == "production" else None,
        }
    if agent_name == "dev":
        out = await DevAgent(llm=llm, sandbox=_NoopSandbox()).run("plano")
        return {
            "content": out.model_dump_json(),
            "confidence": 0.0,
            "critical_alerts": 0,
        }
    raise ValueError(f"agente desconhecido: {agent_name}")


class _NoopSandbox:
    async def validate(self, code: str) -> dict:
        return {"success": True, "stderr": ""}
