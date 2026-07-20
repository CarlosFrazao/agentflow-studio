"""Endpoint /run — orquestrador (máquina de estados) exposto via API.

Executa o agente especialista da coluna atual do card, persiste o Artifact e
a Execution, avança o card para a próxima coluna e aplica auto-approve (ADR-007)
quando confidence >= 0.85 e sem alertas críticos do Reviewer.
"""

from datetime import datetime, timezone, timedelta
import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_owned_card, get_request_id
from app.services.deps import (
    get_firecrawl,
    get_github,
    get_llm,
    get_sandbox,
    get_sra,
)
from app.core.database import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.responses import sanitize_error, success_envelope
from app.services.learning_memory import LearningMemory
from app.models.artifact import Artifact
from app.models.card import Card
from app.models.execution import Execution
from app.services.agents.code_research import CodeResearchAgent
from app.services.agents.dev import DevAgent
from app.services.agents.ideation import IdeationAgent
from app.services.agents.planner import PlannerAgent
from app.services.agents.research import ResearchAgent
from app.services.agents.reviewer import ReviewerAgent
from app.services.orchestrator import (
    next_agent_for_column,
    next_column,
    should_auto_approve,
    column_after_review,
)
from app.services.pipeline_helpers import (
    latest_artifact_content,
    parse_ideation,
    budget_remaining_usd,
    maybe_compress,
)

router = APIRouter(prefix="/cards", tags=["run"])
logger = get_logger("run_endpoint")

AUTO_APPROVE_REVERT_WINDOW_MIN = 30


@router.post("/{card_id}/run", response_model=None)
async def run_card(
    card: Card = Depends(get_owned_card),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    llm=Depends(get_llm),
    sra=Depends(get_sra),
    firecrawl=Depends(get_firecrawl),
    github=Depends(get_github),
    sandbox=Depends(get_sandbox),
) -> dict:
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
            agent_name, card, llm, sra, firecrawl, github, sandbox, session
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
        # Tarefa B (D2): registra a falha na memória de aprendizado (gravação
        # síncrona em markdown via thread separada — não bloqueia o loop).
        # Fail-open: nunca interrompe o pipeline se a gravação falhar.
        try:
            await asyncio.to_thread(
                LearningMemory().record_lesson, agent_name, f"falha: {exc}"
            )
        except Exception as lesson_exc:
            logger.warning("record_lesson_failed", error=str(lesson_exc))
        return success_envelope(
            data={
                "status": "failed",
                "agent": agent_name,
                "error": sanitize_error(exc),
                "request_id": request_id,
            },
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

    # ADR A4 (FEAT-004): only overwrite confidence when the dispatched agent
    # returns a positive signal. Agents like planner/dev return 0.0 (no
    # confidence of their own), which must NOT zero out the Reviewer's score.
    if confidence > 0:
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
    else:
        # Audit BUG-005: limpa flag de auto-approve se o agente reprovar
        # (ex.: Reviewer com alertas críticos após ciclo review->dev).
        # Sem isso, o card ficaria "auto_approved" zombie indevidamente.
        card.auto_approved = False
        card.approval_by = "none"
        card.revert_deadline = None
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


async def _dispatch(agent_name, card, llm, sra, firecrawl, github, sandbox, session):
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
            code_out = await CodeResearchAgent(
                llm=llm, github=github, firecrawl=firecrawl
            ).run(query=card.title, per_page=3)
            logger.debug(
                "code_research_done",
                card=str(card.id),
                suggestions=len(code_out.suggestions),
                license_class=code_out.license_class,
                degraded=code_out.degraded,
            )
            if code_out.suggestions or code_out.license_class != "unknown":
                result["extra_artifacts"].append(
                    {
                        "agent_name": "code_research",
                        "content": code_out.model_dump_json(),
                    }
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
        budget_remaining = await budget_remaining_usd(session, card)
        research_content = await latest_artifact_content(session, card.id, "research")
        cr_content = await latest_artifact_content(session, card.id, "code_research")
        research_compressed = await maybe_compress(
            research_content or "", budget_remaining
        )
        cr_compressed = await maybe_compress(cr_content or "", budget_remaining)
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
            ideation=await parse_ideation(
                await latest_artifact_content(session, card.id, "ideation")
            ),
            research=research_compressed,
            code_research=cr_compressed,
        )
        return {
            "content": out.model_dump_json(),
            "confidence": 0.0,
            "critical_alerts": 0,
        }
    if agent_name == "reviewer":
        # Reviewer audita a consistência Ideia→Pesquisa→Plano→Code Research.
        # Recebe os artifacts reais de cada agente (não vazios) — só assim ele
        # detecta inconsistências reais entre as etapas (PRD F-005).
        ideation_content = await latest_artifact_content(session, card.id, "ideation")
        research_content = await latest_artifact_content(session, card.id, "research")
        planner_content = await latest_artifact_content(session, card.id, "planner")
        cr_content = await latest_artifact_content(session, card.id, "code_research")
        out = await ReviewerAgent(llm=llm).run(
            ideation=await parse_ideation(ideation_content),
            research=research_content or "",
            planner=planner_content or "",
            code_research=cr_content or "",
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
        # Dev Agent consome o plano REAL do Planner Agent (não a string fixa
        # "plano") e valida em sandbox real (DockerSandbox via get_sandbox_backend,
        # injetável nos testes). O plano é o conteúdo do artifact "planner".
        planner_content = await latest_artifact_content(session, card.id, "planner")
        plan = planner_content or ""
        out = await DevAgent(llm=llm, sandbox=sandbox).run(plan)
        return {
            "content": out.model_dump_json(),
            "confidence": 0.0,
            "critical_alerts": 0,
        }
    raise ValueError(f"agente desconhecido: {agent_name}")
