"""Conductor — Orquestração Conversacional multi-turno (F-023).

O Conductor é um agente orquestrador conversacional, NÃO um agente a mais na
pipeline. Ele recebe mensagens do usuário, decide quais ferramentas (wrappers
finos sobre os agents reais do pipeline) executar, respeita a tabela de
dependências e avança o mesmo `Card` do Kanban — logo o board reflete o chat
em tempo real, sem lógica extra.

Decisão de arquitetura (Plano F-023 §1): o `llm.py` NÃO suporta tool-use
nativo. O Conductor pede ao LLM, via `generate_json`, um objeto estruturado
com `tool_calls`; o backend interpreta, executa os agents reais e re-injeta o
resultado. Sempre com fail-open: JSON malformado cai no plano determinístico
pela coluna atual do card (a tabela de dependências), nunca quebrando o pipeline.

Constantes de auto-approve (ADR-007) são REAPROVEITADAS de `orchestrator.py`
(Plano F-023 §3.4) — não duplicadas.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.artifact import Artifact
from app.models.card import Card
from app.models.conversation import Conversation, Message
from app.services.orchestrator import (
    AUTO_APPROVE_CONFIDENCE_THRESHOLD,
    column_after_review,
    next_column,
    should_auto_approve,
)
from app.services.pipeline_helpers import (
    budget_remaining_usd,
    latest_artifact_content,
    maybe_compress,
    parse_ideation,
)
from app.services.event_bus import Event, event_bus

logger = get_logger("conductor")

# Janela de reversão do auto-approve (idêntica ao /run).
AUTO_APPROVE_REVERT_WINDOW_MIN = 30

# Ferramentas suportadas pelo Conductor.
TOOL_IDEATION = "run_ideation"
TOOL_RESEARCH = "run_research"
TOOL_CODE_RESEARCH = "run_code_research"
TOOL_PLANNER = "run_planner"
TOOL_REVIEWER = "run_reviewer"
TOOL_DEV = "run_dev"
TOOL_GET_CARD_STATE = "get_card_state"
TOOL_ASK_USER = "ask_user"
TOOL_CONFIRM_IDEATION = "confirm_ideation"
TOOL_ANSWER = "answer_question"

# Mapeia a coluna atual do card para o conjunto determinístico de ferramentas.
# Ideation cria o card, então a etapa inicial (sem card) força run_ideation.
# Em "backlog" com card já criado, o Conductor pausa e oferece confirm_ideation
# (FEAT-005): o card NÃO avança automaticamente após a ideation.
COLUMN_TO_TOOLS: dict[str, list[str]] = {
    "backlog": [TOOL_IDEATION, TOOL_CONFIRM_IDEATION],
    "researching": [TOOL_RESEARCH, TOOL_CODE_RESEARCH],
    "planning": [TOOL_PLANNER],
    "reviewing": [TOOL_REVIEWER],
    "production": [TOOL_DEV],
    "done": [TOOL_GET_CARD_STATE],
}

_SYSTEM_PROMPT = (
    "Você é o Conductor do AgentFlow Studio: um orquestrador conversacional que "
    "conduz a ideia do usuário pelo pipeline de agentes (Ideation -> Research + "
    "Code Research -> Planner -> Reviewer -> Dev). Responda APENAS em JSON com o "
    'schema: {"narrative": str, "tool_calls": [{"tool": str, "input": {}}]}. '
    "Regras de orquestração: (1) uma ideia nova sem card ainda criado exige "
    '"run_ideation"; (2) na coluna "researching" rode "run_research" e '
    '"run_code_research" juntos; (3) na coluna "planning" rode "run_planner"; '
    '(4) na coluna "reviewing" rode "run_reviewer"; (5) se o Reviewer emitir '
    'alerta crítico, PARE e use "ask_user" (não decida sozinho); (6) na coluna '
    '"production" rode "run_dev"; (7) use "get_card_state" para consultar o '
    'card; (8) quando a ideation já rodou e o card está em "backlog" aguardando '
    'sua confirmação, use "confirm_ideation" para avançar para "researching" '
    '(se o usuário enviar correções, elas são aplicadas antes de avançar). (9) '
    "quando o usuário fizer uma pergunta ou discussão sobre o que já foi feito "
    "(sem intenção de avançar o pipeline), use \"answer_question\" com "
    '"tool_calls":[] e apenas "narrative" — NÃO rode o próximo agente nem avance '
    'o card. Nunca invente ferramentas fora desta lista.'
)


def _default_plan_for_column(column: str | None, has_card: bool = False) -> list[str]:
    """Plano determinístico de fail-open pela coluna atual do card.

    Em "backlog" a ideation cria o card, mas por design (FEAT-005) a ideation
    NÃO avança o card — ela pausa. Quando já existe um card em backlog (a
    ideation já rodou e pausou), o fail-open confirma/avança para researching
    em vez de recriar um card (evita loop de cards duplicados).
    """
    if column is None:
        return [TOOL_IDEATION]
    if column == "backlog" and has_card:
        return [TOOL_CONFIRM_IDEATION]
    return COLUMN_TO_TOOLS.get(column, [TOOL_GET_CARD_STATE])


class Conductor:
    """Orquestrador conversacional com estado, por conversa.

    Cada instância opera sobre uma `Conversation` (e seu `Card` opcional) numa
    sessão de DB. As ferramentas são wrappers finos sobre os agents reais.
    """

    def __init__(
        self,
        conversation: Conversation,
        session: AsyncSession,
        *,
        llm,
        sra,
        firecrawl,
        github,
        sandbox,
        now=time.monotonic,
    ) -> None:
        self._conversation = conversation
        self._session = session
        self._llm = llm
        self._sra = sra
        self._firecrawl = firecrawl
        self._github = github
        self._sandbox = sandbox
        self._now = now
        # Timestamps de início por tool neste turno (prova de paralelismo).
        self._tool_started_at: dict[str, float] = {}

    # ------------------------------------------------------------------
    # API pública (multi-turno)
    # ------------------------------------------------------------------

    async def handle_turn(self, user_message: str) -> dict[str, Any]:
        """Processa um turno: planeja, executa tools, persiste e devolve o resumo.

        Retorna um dict serializável (ver ConductorTurnResponse):
          {conductor_reply, tool_calls, card_id, awaiting_user}
        """
        # Persiste a entrada do usuário (transparência do chat).
        await self._save_message("user", content=user_message)

        card = await self._load_card()
        column = card.column if card else None

        # 1) Plano: LLM (JSON manual) com fallback determinístico por coluna.
        plan = await self._plan(user_message, column)
        tool_names = [tc.tool for tc in plan.tool_calls] or _default_plan_for_column(
            column, has_card=card is not None
        )
        # FEAT-004: resposta livre — se o LLM sinalizou answer_question, ele foi o
        # único tool indicado (tool_calls vazio ou [answer_question]). Nesse ramo o
        # Conductor apenas responde narrativamente, sem rodar agente nem avançar o card.
        if plan.tool_calls and all(tc.tool == TOOL_ANSWER for tc in plan.tool_calls):
            tool_names = [TOOL_ANSWER]

        # 2) Executa as tools indicadas.
        executed: list[dict[str, Any]] = []
        awaiting_user = False
        awaiting_confirmation = False
        # Research + Code Research rodam EM PARALELO (asyncio.gather) — prova de
        # paralelismo real: seus started_at ficam sobrepostos (Plano F-023 §3.2).
        parallel_names = [TOOL_RESEARCH, TOOL_CODE_RESEARCH]
        parallel_set = {n for n in tool_names if n in parallel_names}
        sequential = [n for n in tool_names if n not in parallel_names]

        if len(parallel_set) == 2:
            parallel_results = await self._run_parallel(parallel_set, card)
            for result in parallel_results:
                executed.append(result)
                card = result.get("card") or card
                await self._save_message(
                    "tool",
                    content=self._tool_summary(result),
                    tool_name=result.get("tool"),
                    tool_input=result.get("input"),
                    tool_output=result.get("output"),
                )
                if result.get("critical_alert"):
                    awaiting_user = True

        tool_input_by_name = {tc.tool: tc.input for tc in plan.tool_calls}

        for name in sequential:
            if name == TOOL_ASK_USER:
                awaiting_user = True
                continue
            result = await self._run_tool(name, card, tool_input_by_name.get(name, {}))
            executed.append(result)
            card = result.get("card") or card
            # Transparência: cada tool vira uma Message(role=tool).
            await self._save_message(
                "tool",
                content=self._tool_summary(result),
                tool_name=result.get("tool"),
                tool_input=result.get("input"),
                tool_output=result.get("output"),
            )
            # Se um Reviewer crítico for detectado, o Conductor para e pergunta.
            if result.get("critical_alert"):
                awaiting_user = True
            # FEAT-005: pausa pós-ideation — o card aguarda confirmação do usuário.
            # Inclui o branch de clarificação (FEAT-001): ideia vaga também pausa.
            if result.get("awaiting_confirmation") or result.get("awaiting_clarification"):
                awaiting_confirmation = True

        # 3) Narrativa: usa a do plano (LLM) ou gera a partir dos resultados.
        narrative = plan.narrative
        if not narrative:
            narrative = self._synthesize_narrative(executed, awaiting_user)

        # Persiste a resposta consolidada do Conductor.
        await self._save_message("conductor", content=narrative)

        self._conversation = await self._reload_conversation()
        return {
            "conductor_reply": narrative,
            "tool_calls": executed,
            "card_id": self._conversation.card_id,
            "awaiting_user": awaiting_user,
            "awaiting_confirmation": awaiting_confirmation,
        }

    def _tool_summary(self, result: dict[str, Any]) -> str:
        """Texto curto exibido na bolha de tool do chat (Plano F-023 §6)."""
        tool = result.get("tool", "tool")
        out = result.get("output", {}) or {}
        if tool == TOOL_IDEATION:
            return f"Ideation: {out.get('project_name', 'projeto')} estruturado"
        if tool == TOOL_RESEARCH:
            return "Research Agent concluído"
        if tool == TOOL_CODE_RESEARCH:
            sugg = len(out.get("suggestions", []) or [])
            return f"Code Research concluído ({sugg} sugestões)"
        if tool == TOOL_PLANNER:
            return "Planner Agent concluído"
        if tool == TOOL_REVIEWER:
            crit = out.get("critical_count", 0)
            return f"Reviewer concluído ({crit} alertas críticos)"
        if tool == TOOL_DEV:
            ok = out.get("sandbox_success")
            return "Dev Agent concluído" if ok else "Dev Agent (validação pendente)"
        return tool

    async def _save_message(
        self,
        role: str,
        *,
        content: str = "",
        tool_name: str | None = None,
        tool_input: dict | None = None,
        tool_output: dict | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=self._conversation.id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
        )
        self._session.add(msg)
        await self._session.commit()
        await self._session.refresh(msg)
        return msg

    # ------------------------------------------------------------------
    # Planejamento (LLM JSON + fail-open)
    # ------------------------------------------------------------------

    async def _plan(self, user_message: str, column: str | None) -> Any:
        """Pede ao LLM o plano de tool_calls; falha para o determinístico."""
        state = (
            f"coluna atual do card: {column or 'sem card'}"
            if column is not None
            else "ainda não há card (ideia nova)"
        )
        # FEAT-003: injeta o histórico recente da conversa (fail-open: vazio =
        # não quebra o prompt, apenas não adiciona contexto).
        history = self._format_history(await self._recent_messages())
        user_prompt = f"{state}\n{history}\nmensagem do usuario: {user_message}"
        try:
            data = await self._llm.generate_json(
                system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt
            )
            plan = self._validate_plan(data, column)
            if plan is not None:
                return plan
        except Exception as exc:  # noqa: BLE001
            logger.warning("conductor_plan_llm_failed", error=str(exc))
        # Fail-open: plano determinístico pela coluna.
        # column is not None => já existe um card (a coluna vem do card); nas
        # colunas válidas, um card em backlog com ideation já rodada deve
        # confirmar/avançar (FEAT-005) em vez de recriar o card.
        tools = _default_plan_for_column(column, has_card=column is not None)
        return _StubPlan(tools)

    def _validate_plan(self, data: dict, column: str | None) -> Any | None:
        """Valida o JSON do LLM contra o schema; None se inválido/vazio."""
        try:
            plan = _ConductorPlanShim(**data)
        except Exception:  # noqa: BLE001
            return None
        calls = [c for c in plan.tool_calls if c.tool in COLUMN_TO_TOOLS.get(column or "", []) or c.tool in (TOOL_ASK_USER, TOOL_GET_CARD_STATE, TOOL_CONFIRM_IDEATION, TOOL_ANSWER)]
        # Se o card ainda não existe, só run_ideation é aceitável como primeira ação.
        if column is None and calls and calls[0].tool != TOOL_IDEATION:
            return None
        if not calls:
            return None
        return plan

    # ------------------------------------------------------------------
    # Histórico da conversa (FEAT-003 — memória de curto prazo no prompt)
    # ------------------------------------------------------------------

    async def _recent_messages(self, limit: int = 10) -> list[Message]:
        """Retorna as `limit` mensagens mais recentes em ordem cronológica.

        Ordena por `created_at DESC, id DESC` (o id é uuid4, não ordenável no
        tempo — por isso `created_at` é a chave primária de ordenação, com o id
        só como desempate estável). O resultado é revertido para ordem
        cronológica (mais antiga primeiro).
        """
        stmt = (
            select(Message)
            .where(Message.conversation_id == self._conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        rows = (await self._session.scalars(stmt)).all()
        return list(reversed(rows))

    def _format_history(self, msgs: list[Message]) -> str:
        """Formata as mensagens como `{role}: {content}`.

        Mensagens de tool incluem o nome da tool e um resumo do output. Lista
        vazia retorna string vazia (fail-open).
        """
        if not msgs:
            return ""
        lines: list[str] = []
        for m in msgs:
            if m.role == "tool":
                summary = ""
                if isinstance(m.tool_output, dict):
                    summary = ", ".join(
                        f"{k}={v}" for k, v in list(m.tool_output.items())[:3]
                    )
                label = m.tool_name or "tool"
                content = m.content or summary
                lines.append(f"tool[{label}]: {content}".rstrip(": ").rstrip())
            else:
                lines.append(f"{m.role}: {m.content}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Execução de ferramentas (wrappers finos sobre agents reais)
    # ------------------------------------------------------------------

    async def _run_tool(
        self, name: str, card: Card | None, user_input: dict | None = None
    ) -> dict[str, Any]:
        self._tool_started_at[name] = self._now()
        if name == TOOL_IDEATION:
            return await self._tool_ideation()
        if name == TOOL_RESEARCH:
            return await self._tool_research(card)
        if name == TOOL_CODE_RESEARCH:
            return await self._tool_code_research(card)
        if name == TOOL_PLANNER:
            return await self._tool_planner(card)
        if name == TOOL_REVIEWER:
            return await self._tool_reviewer(card)
        if name == TOOL_DEV:
            return await self._tool_dev(card)
        if name == TOOL_GET_CARD_STATE:
            return await self._tool_card_state(card)
        if name == TOOL_CONFIRM_IDEATION:
            return await self._tool_confirm_ideation(card, user_input or {})
        if name == TOOL_ANSWER:
            return self._tool_answer_question(card)
        return {"tool": name, "input": {}, "output": {}, "card": card}

    async def _run_parallel(
        self, names: set[str], card: Card | None
    ) -> list[dict[str, Any]]:
        """Executa Research + Code Research em paralelo via asyncio.gather.

        Os AGENTES rodam concorrentemente (prova de paralelismo real: ambos
        iniciam quase juntos). A PERSISTÊNCIA/avanço do card é aplicada em
        sequência APÓS o gather, para não conflitar a transação da sessão
        (dois commits concorrentes na mesma AsyncSession quebram o flush). O
        `code_research` é artifact AUXILIAR (como no /run): só o `research`
        avança a coluna do card.
        """
        import asyncio

        # 1) Execução concorrente dos agents (sem tocar a sessão).
        outs = await asyncio.gather(
            self._exec_research(card),
            self._exec_code_research(card),
        )
        # 2) Aplicação serial (persistência + avanço de coluna).
        r_research = await self._apply_research(card, outs[0])
        r_code = await self._apply_code_research(card, outs[1])
        # Ordem estável para exibição no chat: research antes de code_research.
        return [r_research, r_code]

    async def _tool_ideation(self) -> dict[str, Any]:
        """Cria o Card real em backlog, roda o Ideation e avança para researching."""
        from app.services.agents.ideation import IdeationAgent

        card = Card(
            project_id=self._conversation.project_id,
            column="backlog",
            title="Ideia do Conductor",
        )
        self._session.add(card)
        await self._session.commit()
        await self._session.refresh(card)

        out = await IdeationAgent(llm=self._llm).run(card.title)
        await self._persist_artifact(
            card, "ideation", out.model_dump_json(), confidence=out.confidence_score
        )
        card.confidence_score = out.confidence_score

        if out.needs_clarification:
            # Ideia vaga/contraditória: NÃO avança para researching. O card
            # permanece em backlog e expõe as open_questions ao usuário (FEAT-001).
            await self._session.commit()
            await self._session.refresh(card)
            self._conversation.card_id = card.id
            await self._session.commit()
            self._publish_card_updated(card)
            return {
                "tool": TOOL_IDEATION,
                "input": {"title": card.title},
                "output": {
                    "project_name": out.project_name,
                    "key_features": out.key_features,
                    "elevator_pitch": out.elevator_pitch,
                    "confidence_score": out.confidence_score,
                    "open_questions": out.open_questions,
                },
                "card": card,
                "awaiting_clarification": True,
            }

        # Ideia clara: FEAT-005 — NÃO avança o card. A ideation pausa em backlog
        # e aguarda confirmação do usuário (confirm_ideation) antes de prosseguir
        # para researching (permite correções antes do pipeline caro rodar).
        await self._session.commit()
        await self._session.refresh(card)

        # Ata o card à conversa (Plano F-023 §4).
        self._conversation.card_id = card.id
        await self._session.commit()
        self._publish_card_updated(card)

        return {
            "tool": TOOL_IDEATION,
            "input": {"title": card.title},
            "output": {
                "project_name": out.project_name,
                "key_features": out.key_features,
                "elevator_pitch": out.elevator_pitch,
                "confidence_score": out.confidence_score,
                "open_questions": out.open_questions,
            },
            "card": card,
            "awaiting_confirmation": True,
        }

    async def _tool_confirm_ideation(
        self, card: Card | None, user_input: dict
    ) -> dict[str, Any]:
        """Confirma a ideation pausada e avança o card para researching (FEAT-005).

        Se o usuário enviou correções (user_input["corrections"]), a Ideation é
        re-executada com o título ajustado antes de avançar o card.
        """
        if card is None:
            return self._no_card(TOOL_CONFIRM_IDEATION)

        corrections = (user_input or {}).get("corrections")
        if corrections:
            from app.services.agents.ideation import IdeationAgent

            # Re-roda a Ideation com o contexto corrigido do usuário.
            refined_title = f"{card.title} — {corrections}"
            out = await IdeationAgent(llm=self._llm).run(refined_title)
            await self._persist_artifact(
                card, "ideation", out.model_dump_json(), confidence=out.confidence_score
            )
            card.confidence_score = out.confidence_score
            card.title = refined_title

        # Avança o card (backlog -> researching) após a confirmação do usuário.
        card.column = next_column(card.column)
        await self._session.commit()
        await self._session.refresh(card)
        self._publish_card_updated(card)

        return {
            "tool": TOOL_CONFIRM_IDEATION,
            "input": user_input or {},
            "output": {"confirmed": True},
            "card": card,
        }

    # --- Research / Code Research: exec (paralelo) + apply (serial) ---

    async def _exec_research(self, card: Card | None):
        from app.services.agents.research import ResearchAgent

        if card is None:
            return None
        return await ResearchAgent(llm=self._llm, sra=self._sra).run(card.title)

    async def _apply_research(self, card: Card | None, out) -> dict[str, Any]:
        if card is None or out is None:
            return self._no_card(TOOL_RESEARCH)
        await self._persist_artifact(
            card, "research", out.model_dump_json(), confidence=out.confidence
        )
        # Só o research avança a coluna (code_research é auxiliar, como no /run).
        await self._advance_after(card, "research", out.confidence)
        self._publish_card_updated(card)
        return {
            "tool": TOOL_RESEARCH,
            "input": {"query": card.title, "mode": "guerrilha"},
            "output": {
                "confidence": out.confidence,
                "degraded": out.degraded,
                "warning": out.warning,
            },
            "card": card,
        }

    async def _exec_code_research(self, card: Card | None):
        from app.services.agents.code_research import CodeResearchAgent

        if card is None:
            return None
        return await CodeResearchAgent(
            llm=self._llm, github=self._github, firecrawl=self._firecrawl
        ).run(query=card.title, per_page=3)

    async def _apply_code_research(self, card: Card | None, out) -> dict[str, Any]:
        if card is None or out is None:
            return self._no_card(TOOL_CODE_RESEARCH)
        if out.suggestions or out.license_class != "unknown":
            await self._persist_artifact(card, "code_research", out.model_dump_json())
        # NÃO avança a coluna: code_research é artifact auxiliar (igual ao /run).
        return {
            "tool": TOOL_CODE_RESEARCH,
            "input": {"query": card.title, "per_page": 3},
            "output": {
                "suggestions": out.suggestions,
                "license_class": out.license_class,
                "degraded": out.degraded,
                "source_url": out.source_url,
            },
            "card": card,
        }

    async def _tool_research(self, card: Card | None) -> dict[str, Any]:
        out = await self._exec_research(card)
        return await self._apply_research(card, out)

    async def _tool_code_research(self, card: Card | None) -> dict[str, Any]:
        out = await self._exec_code_research(card)
        return await self._apply_code_research(card, out)

    async def _tool_planner(self, card: Card | None) -> dict[str, Any]:
        from app.services.agents.planner import PlannerAgent

        if card is None:
            return self._no_card(TOOL_PLANNER)
        budget_remaining = await budget_remaining_usd(self._session, card)
        research_content = await latest_artifact_content(self._session, card.id, "research")
        cr_content = await latest_artifact_content(self._session, card.id, "code_research")
        research_compressed = await maybe_compress(research_content or "", budget_remaining)
        cr_compressed = await maybe_compress(cr_content or "", budget_remaining)
        out = await PlannerAgent(llm=self._llm).run(
            ideation=await parse_ideation(
                await latest_artifact_content(self._session, card.id, "ideation")
            ),
            research=research_compressed,
            code_research=cr_compressed,
        )
        await self._persist_artifact(card, "planner", out.model_dump_json())
        await self._advance_after(card, "planner", 0.0)
        self._publish_card_updated(card)
        return {
            "tool": TOOL_PLANNER,
            "input": {},
            "output": {
                "title": out.title,
                "stack": out.stack,
                "milestones": out.milestones,
                "risks": out.risks,
            },
            "card": card,
        }

    async def _tool_reviewer(self, card: Card | None) -> dict[str, Any]:
        from app.services.agents.reviewer import ReviewerAgent

        if card is None:
            return self._no_card(TOOL_REVIEWER)
        ideation_content = await latest_artifact_content(self._session, card.id, "ideation")
        research_content = await latest_artifact_content(self._session, card.id, "research")
        planner_content = await latest_artifact_content(self._session, card.id, "planner")
        cr_content = await latest_artifact_content(self._session, card.id, "code_research")
        out = await ReviewerAgent(llm=self._llm).run(
            ideation=await parse_ideation(ideation_content),
            research=research_content or "",
            planner=planner_content or "",
            code_research=cr_content or "",
        )
        await self._persist_artifact(card, "reviewer", out.model_dump_json())
        critical_alert = out.critical_count > 0

        if critical_alert:
            # Alerta crítico: NÃO avança — o Conductor pergunta ao usuário.
            alert_messages = [a.message for a in out.alerts if a.severity == "critical"]
            return {
                "tool": TOOL_REVIEWER,
                "input": {},
                "output": {
                    "passed": out.passed,
                    "critical_count": out.critical_count,
                    "alerts": alert_messages,
                },
                "card": card,
                "critical_alert": True,
            }

        target_col = column_after_review(
            confidence_score=out.confidence_score,
            critical_alerts=out.critical_count,
            review_passed=out.passed,
        )
        card.column = target_col
        card.confidence_score = out.confidence_score
        review_logs = out.log_summary if target_col == "production" else None
        if review_logs is not None:
            meta = dict(card.meta or {})
            meta["review_logs"] = review_logs
            card.meta = meta
        if should_auto_approve(out.confidence_score, out.critical_count):
            card.approval_by = "auto"
            card.auto_approved = True
            card.revert_deadline = datetime.now(tz=timezone.utc) + timedelta(
                minutes=AUTO_APPROVE_REVERT_WINDOW_MIN
            )
        await self._session.commit()
        await self._session.refresh(card)
        self._publish_card_updated(card)
        return {
            "tool": TOOL_REVIEWER,
            "input": {},
            "output": {
                "passed": out.passed,
                "critical_count": out.critical_count,
                "confidence_score": out.confidence_score,
                "target_column": target_col,
            },
            "card": card,
        }

    async def _tool_dev(self, card: Card | None) -> dict[str, Any]:
        from app.services.agents.dev import DevAgent

        if card is None:
            return self._no_card(TOOL_DEV)
        planner_content = await latest_artifact_content(self._session, card.id, "planner")
        out = await DevAgent(llm=self._llm, sandbox=self._sandbox).run(
            planner_content or ""
        )
        await self._persist_artifact(card, "dev", out.model_dump_json())
        await self._advance_after(card, "dev", 0.0)
        self._publish_card_updated(card)
        return {
            "tool": TOOL_DEV,
            "input": {},
            "output": {
                "ran_in_sandbox": out.ran_in_sandbox,
                "sandbox_success": out.sandbox_success,
                "attempts": out.attempts,
            },
            "card": card,
        }

    async def _tool_card_state(self, card: Card | None) -> dict[str, Any]:
        if card is None:
            return {"tool": TOOL_GET_CARD_STATE, "input": {}, "output": {"exists": False}, "card": None}
        return {
            "tool": TOOL_GET_CARD_STATE,
            "input": {},
            "output": {
                "exists": True,
                "column": card.column,
                "title": card.title,
                "confidence_score": card.confidence_score,
                "auto_approved": card.auto_approved,
            },
            "card": card,
        }

    def _tool_answer_question(self, card: Card | None) -> dict[str, Any]:
        """Responde narrativamente a uma pergunta/discussão (FEAT-004, C2).

        Não executa nenhum agente e NÃO avança o card — apenas persiste a
        narrative (feita em handle_turn) e devolve o card sem alteração de coluna.
        """
        return {
            "tool": TOOL_ANSWER,
            "input": {},
            "output": {"answered": True},
            "card": card,
        }

    def _no_card(self, tool: str) -> dict[str, Any]:
        logger.warning("conductor_tool_without_card", tool=tool)
        return {"tool": tool, "input": {}, "output": {"error": "no_card"}, "card": None}

    # ------------------------------------------------------------------
    # Persistência de estado e artifacts
    # ------------------------------------------------------------------

    async def _persist_artifact(
        self, card: Card, agent_name: str, content: str, *, confidence: float = 0.0
    ) -> None:
        self._session.add(
            Artifact(card_id=card.id, agent_name=agent_name, type="json", content=content)
        )
        await self._session.commit()

    def _publish_card_updated(self, card: Card) -> None:
        """Publica card.updated no EventBus para o WebSocket de tempo real.

        Reusa o mesmo tipo de evento que `cards.py` emite, para que o
        `share_ws` (que filtra por project_id) transmita a mudança de coluna/
        confidence ao board sem refresh manual.
        """
        event_bus.publish(
            Event(
                type="card.updated",
                payload={
                    "card_id": str(card.id),
                    "project_id": str(card.project_id),
                    "column": card.column,
                    "confidence_score": card.confidence_score,
                    "auto_approved": card.auto_approved,
                },
            )
        )

    async def _advance_after(
        self, card: Card, agent_name: str, confidence: float
    ) -> None:
        """Avança o card uma coluna após um agente não-reviewer (espelha /run).

        Aplica confidence e persiste (commit + refresh) para manter o estado do
        card coerente com o Kanban em tempo real.
        """
        card.column = next_column(card.column)
        if confidence:
            card.confidence_score = confidence
        self._session.add(card)
        await self._session.commit()
        await self._session.refresh(card)

    async def _load_card(self) -> Card | None:
        if self._conversation.card_id is None:
            return None
        return await self._session.get(Card, self._conversation.card_id)

    async def _reload_conversation(self) -> Conversation:
        refreshed = await self._session.get(Conversation, self._conversation.id)
        return refreshed or self._conversation

    def _synthesize_narrative(
        self, executed: list[dict[str, Any]], awaiting_user: bool
    ) -> str:
        """Gera narrativa a partir dos resultados quando o LLM não a fornece."""
        if awaiting_user:
            return (
                "O Reviewer apontou um alerta crítico. Preciso que você decida como "
                "prosseguir antes de avançar o card."
            )
        if not executed:
            return "Não há o que executar neste momento. O card já está concluído."
        parts = []
        for r in executed:
            tool = r.get("tool", "")
            out = r.get("output", {}) or {}
            if tool == TOOL_IDEATION:
                parts.append(
                    f"Ideia estruturada: {out.get('project_name', 'projeto')} "
                    f"(confiança {out.get('confidence_score', 0):.2f})."
                )
            elif tool == TOOL_RESEARCH:
                parts.append("Pesquisa de mercado concluída.")
            elif tool == TOOL_CODE_RESEARCH:
                parts.append("Pesquisa de código concluída.")
            elif tool == TOOL_PLANNER:
                stack = ", ".join(out.get("stack", []) or [])
                parts.append(f"Plano técnico pronto (stack: {stack or 'n/a'}).")
            elif tool == TOOL_REVIEWER:
                parts.append("Revisão concluída.")
            elif tool == TOOL_DEV:
                ok = out.get("sandbox_success")
                parts.append(
                    "Código gerado e validado no sandbox."
                    if ok
                    else "Código gerado (validação pendente)."
                )
        return " ".join(parts) if parts else "Concluído."


# ----------------------------------------------------------------------
# Shims de validação (mantêm o módulo independente de imports pesados)
# ----------------------------------------------------------------------

class _ConductorPlanShim:
    """Validador mínimo do JSON do LLM (fail-open amigável)."""

    def __init__(self, **data: Any) -> None:
        self.narrative = str(data.get("narrative", "") or "")
        raw_calls = data.get("tool_calls", []) or []
        self.tool_calls: list[_ToolCallShim] = []
        if isinstance(raw_calls, list):
            for c in raw_calls:
                if isinstance(c, dict) and "tool" in c:
                    self.tool_calls.append(
                        _ToolCallShim(c["tool"], c.get("input", {}) or {})
                    )


class _ToolCallShim:
    def __init__(self, tool: str, input: dict) -> None:
        self.tool = str(tool)
        self.input = input if isinstance(input, dict) else {}


class _StubPlan:
    """Plano determinístico de fallback (sem LLM)."""

    def __init__(self, tools: list[str]) -> None:
        self.narrative = ""
        self.tool_calls = [_ToolCallShim(t, {}) for t in tools]
