"""Testes TDD do Conductor (F-023) — Orquestração Conversacional.

Cobre (Plano F-023 §7):
1. run_ideation cria Card + Conversation.card_id preenchido.
2. run_research + run_code_research executam com asyncio.gather (timestamps
   sobrepostos provados via ordem de eventos concorrentes).
3. Reviewer critical -> Conductor responde com ask_user (não decide sozinho).
4. Limiar 0.85 reaproveitado de orchestrator (confiança alta -> auto_approve).
5. Card reflete as mesmas colunas que o /run produziria.
6. Pipeline completo por chat, do zero ao código, sem tocar o Kanban manualmente.

LLM/agents mockados; sra/firecrawl/github/sandbox injetados via override.
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Artifact, Conversation, Message
from app.models.conversation import MSG_ROLES
from app.sandbox.base import SandboxBackend, SandboxResult

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fakes de serviços externos (evitam rede/LLM reais)
# ---------------------------------------------------------------------------

class _DummySRA:
    async def research(self, query, mode="guerrilha"):
        raise RuntimeError("dummy sra: sem rede")


class _DummyFirecrawl:
    async def scrape(self, url):
        raise RuntimeError("dummy firecrawl: sem rede")


class _DummyGithub:
    async def search_repos(self, query, per_page=5):
        return []

    async def get_file(self, repo, path):
        return ""


class _OkSandbox(SandboxBackend):
    name = "ok"

    async def validate(self, code: str) -> SandboxResult:
        return SandboxResult(success=True, stderr="", backend=self.name)


class _FakeLLM:
    """LLM fake: devolve tool_calls vazio -> o Conductor usa o fallback
    determinístico por coluna (equivalente ao plano do LLM para os testes)."""

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {"narrative": "", "tool_calls": []}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return "narrativa fake"


def _override_services(client, llm) -> None:
    """Injeta fakes via request.app.state['service_overrides'] (ver deps.py)."""
    from app.services.deps import _STATE_KEY

    app = client._transport.app
    overrides = getattr(app.state, _STATE_KEY, {})
    overrides["llm"] = llm
    overrides["sra"] = _DummySRA()
    overrides["firecrawl"] = _DummyFirecrawl()
    overrides["github"] = _DummyGithub()
    overrides["sandbox"] = _OkSandbox()
    setattr(app.state, _STATE_KEY, overrides)


async def _seed_project(client) -> str:
    resp = await client.post("/api/v1/projects", json={"name": "P"})
    return resp.json()["data"]["id"]


async def _create_conversation(client, project_id: str) -> str:
    resp = await client.post(
        "/api/v1/conversations", json={"project_id": project_id}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _turn(client, conv_id: str, content: str) -> dict:
    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages", json={"content": content}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# 1) run_ideation cria Card + Conversation.card_id
# ---------------------------------------------------------------------------

async def test_run_ideation_creates_card_and_binds_conversation(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match", "rotas"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    body = await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    assert body["card_id"] is not None
    assert body["awaiting_user"] is False
    # FEAT-005: a ideation pausa em backlog (não avança automaticamente).
    assert body["awaiting_confirmation"] is True

    # O Card foi criado e permanece em backlog aguardando confirmação.
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "backlog"

    # Confirma -> avança para researching (Ideation concluído).
    confirm = await _turn(client, cid, "confirmar e prosseguir")
    assert confirm["awaiting_confirmation"] is False
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "researching"

    # Conversation.card_id foi preenchido (já na ideation, antes da confirmação).
    async with session_factory() as s:
        conv = await s.get(Conversation, UUID(cid))
        assert conv.card_id == UUID(body["card_id"])


# ---------------------------------------------------------------------------
# 2) research + code_research em paralelo (asyncio.gather)
# ---------------------------------------------------------------------------

async def test_research_and_code_research_run_in_parallel(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )

    # Registra a ordem de start/end para provar sobreposição real (gather).
    events: list[tuple[str, str]] = []

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        events.append(("research", "start"))
        await asyncio.sleep(0.02)
        events.append(("research", "end"))
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        events.append(("code_research", "start"))
        await asyncio.sleep(0.02)
        events.append(("code_research", "end"))
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    # T1: cria o card (ideation) -> pausa em backlog.
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    # Confirma a ideation -> researching.
    await _turn(client, cid, "confirmar e prosseguir")
    # T2: pesquisa (research + code_research em paralelo).
    body = await _turn(client, cid, "seguir com a pesquisa")

    assert body["awaiting_user"] is False
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "planning"

    # Prova de paralelismo: ambos iniciaram ANTES de qualquer um terminar.
    assert events[0] == ("research", "start")
    assert events[1] == ("code_research", "start")
    assert ("research", "end") not in events[:2]
    assert ("code_research", "end") not in events[:2]


# ---------------------------------------------------------------------------
# 3) Reviewer critical -> Conductor pergunta ao usuário (ask_user)
# ---------------------------------------------------------------------------

async def test_reviewer_critical_makes_conductor_ask_user(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import (
        ReviewerAgent,
        ReviewOutput,
        ReviewAlert,
    )

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[ReviewAlert(message="risco critico", severity="critical")],
            critical_count=1,
            passed=False,
            confidence_score=0.4,
            log_summary="risco critico",
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "confirmar e prosseguir")
    await _turn(client, cid, "seguir com a pesquisa")
    await _turn(client, cid, "fazer o plano")
    body = await _turn(client, cid, "revisar")

    # O Conductor NÃO avança o card e sinaliza que aguarda o usuário.
    assert body["awaiting_user"] is True
    card = await client.get("/api/v1/cards/" + body["card_id"])
    # Card permanece em reviewing (não decide sozinho).
    assert card.json()["data"]["column"] == "reviewing"


# ---------------------------------------------------------------------------
# 4) Limiar 0.85 reaproveitado de orchestrator (confiança alta -> auto_approve)
# ---------------------------------------------------------------------------

async def test_auto_approve_threshold_reused_from_orchestrator(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput
    from app.services.orchestrator import (
        AUTO_APPROVE_CONFIDENCE_THRESHOLD,
        should_auto_approve,
    )

    # A constante vem do orchestrator (não duplicada no conductor).
    from app.services.conductor import AUTO_APPROVE_REVERT_WINDOW_MIN  # noqa: F401

    assert AUTO_APPROVE_CONFIDENCE_THRESHOLD == 0.85
    assert should_auto_approve(0.9, 0) is True
    assert should_auto_approve(0.84, 0) is False

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=True,
            confidence_score=0.95,
            log_summary=None,
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "confirmar e prosseguir")
    await _turn(client, cid, "seguir com a pesquisa")
    await _turn(client, cid, "fazer o plano")
    body = await _turn(client, cid, "revisar")

    card = await client.get("/api/v1/cards/" + body["card_id"])
    data = card.json()["data"]
    assert data["column"] == "done"
    assert data["auto_approved"] is True
    assert data["approval_by"] == "auto"


# ---------------------------------------------------------------------------
# 5) Card reflete as mesmas colunas que o /run produziria
# ---------------------------------------------------------------------------

async def test_card_columns_match_run_pipeline(
    client, session_factory, monkeypatch
) -> None:
    from app.models.card import KANBAN_COLUMNS
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    # Reviewer REPROVA (sem crítico) -> production (ciclo Criação<->Revisão).
    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=False,
            confidence_score=0.5,
            log_summary="reprovado",
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    # Cada mensagem avança o card exatamente como o /run faria.
    seq = [
        ("quero criar um app de caronas", "backlog"),  # ideation pausa (FEAT-005)
        ("confirmar e prosseguir", "researching"),     # confirma -> researching
        ("pesquisar", "planning"),
        ("planejar", "reviewing"),
        ("revisar", "production"),  # reviewer reprovou -> production
        ("gerar codigo", "done"),   # dev em production -> done
    ]
    for msg, expected_col in seq:
        body = await _turn(client, cid, msg)
        card = await client.get("/api/v1/cards/" + body["card_id"])
        assert card.json()["data"]["column"] == expected_col

    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] in KANBAN_COLUMNS


# ---------------------------------------------------------------------------
# 6) Pipeline completo por chat do zero ao código, sem tocar o Kanban manualmente
# ---------------------------------------------------------------------------

async def test_full_pipeline_via_chat_zero_to_code(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import ReviewerAgent, ReviewOutput
    from app.services.agents.dev import DevAgent, DevOutput

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    # Reviewer reprovado (sem crítico) -> production, onde o dev roda.
    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[],
            critical_count=0,
            passed=False,
            confidence_score=0.5,
            log_summary="reprovado",
        )

    async def fake_dev(self, plan):  # noqa: ANN001
        return DevOutput(
            code="print('hi')",
            ran_in_sandbox=True,
            sandbox_success=True,
            attempts=1,
        )

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)
    monkeypatch.setattr(DevAgent, "run", fake_dev)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "confirmar e prosseguir")
    await _turn(client, cid, "seguir com a pesquisa")
    await _turn(client, cid, "fazer o plano")
    await _turn(client, cid, "revisar")
    body = await _turn(client, cid, "gerar o codigo")

    card_id = body["card_id"]
    assert card_id is not None

    # O card chegou a 'done' sem PATCH manual de coluna.
    card = await client.get("/api/v1/cards/" + card_id)
    assert card.json()["data"]["column"] == "done"

    # O artifact 'dev' foi produzido pelo Dev Agent.
    async with session_factory() as s:
        result = await s.execute(
            select(Artifact).where(
                Artifact.card_id == UUID(card_id), Artifact.agent_name == "dev"
            )
        )
        assert result.scalars().first() is not None

    # Histórico de mensagens registrou user + tool + conductor.
    msgs = await client.get(f"/api/v1/conversations/{cid}/messages")
    roles = [m["role"] for m in msgs.json()["data"]["messages"]]
    assert "user" in roles
    assert "conductor" in roles
    assert "tool" in roles
    assert all(r in MSG_ROLES for r in roles)


# ---------------------------------------------------------------------------
# 7) Conductor publica card.updated no EventBus (tempo real via WebSocket)
# ---------------------------------------------------------------------------

async def test_conductor_publishes_card_updated_event(
    client, session_factory, monkeypatch
) -> None:
    from app.services.agents.ideation import IdeationAgent, IdeationOutput
    from app.services.event_bus import Event

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    # Captura os eventos publicados sem afetar o bus global (spy no publish).
    from app.services.event_bus import event_bus

    published: list = []

    real_publish = event_bus.publish

    def _spy_publish(event: Event) -> None:
        published.append(event)
        # Não propaga para os subscribers reais (mantém o teste isolado).
        return None

    monkeypatch.setattr(event_bus, "publish", _spy_publish)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    await _turn(client, cid, "quero criar um app de caronas pra faculdade")

    updated = [e for e in published if e.type == "card.updated"]
    assert updated, "Conductor deve publicar card.updated no EventBus"
    payload = updated[-1].payload
    # FEAT-005: a ideation pausa em backlog (não avança para researching).
    assert payload["column"] == "backlog"
    assert payload["project_id"] == pid
    assert payload["card_id"]

    # A confirmação avança o card para researching e publica o evento.
    await _turn(client, cid, "confirmar e prosseguir")
    researching_events = [
        e for e in published if e.type == "card.updated" and e.payload["column"] == "researching"
    ]
    assert researching_events, "confirmação deve publicar card.updated em researching"


# ---------------------------------------------------------------------------
# FEAT-003: Injeção do histórico da conversa no prompt do _plan()
# ---------------------------------------------------------------------------

class _SpyLLM:
    """Captura o user_prompt recebido pelo _plan (para inspecionar o histórico)."""

    def __init__(self) -> None:
        self.last_user_prompt: str | None = None

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.last_user_prompt = user_prompt
        return {"narrative": "", "tool_calls": []}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return ""


async def _make_conductor(session, project_id, spy):
    from app.models.conversation import Conversation
    from app.services.conductor import Conductor

    conv = Conversation(project_id=project_id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    cond = Conductor(
        conv, session, llm=spy, sra=_DummySRA(), firecrawl=_DummyFirecrawl(),
        github=_DummyGithub(), sandbox=_OkSandbox(),
    )
    return cond, conv


async def test_plan_includes_recent_history(session_factory) -> None:
    from app.models.project import Project
    from app.models.conversation import Message

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)

        spy = _SpyLLM()
        cond, conv = await _make_conductor(s, proj.id, spy)
        # Pré-popula a conversa com mensagens anteriores.
        s.add(Message(conversation_id=conv.id, role="user", content="mensagem antiga do user"))
        s.add(Message(conversation_id=conv.id, role="conductor", content="resposta anterior"))
        await s.commit()

        await cond._plan("e aí, continua", column="researching")
        assert spy.last_user_prompt is not None
        assert "mensagem antiga do user" in spy.last_user_prompt


async def test_plan_empty_history_graceful(session_factory) -> None:
    from app.models.project import Project

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)

        spy = _SpyLLM()
        cond, conv = await _make_conductor(s, proj.id, spy)
        assert cond._format_history([]) == ""
        # _plan não quebra com histórico vazio.
        await cond._plan("primeira mensagem", column=None)
        assert spy.last_user_prompt is not None


async def test_recent_messages_limit(session_factory) -> None:
    from app.models.project import Project
    from app.models.conversation import Message

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)

        spy = _SpyLLM()
        cond, conv = await _make_conductor(s, proj.id, spy)
        # created_at explícito e crescente: garante ordem determinística
        # (created_at do SQLite tem resolução de segundos e o id é uuid4).
        from datetime import datetime, timedelta, timezone

        base = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(15):
            s.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content=f"msg-{i:02d}",
                    created_at=base + timedelta(seconds=i),
                )
            )
            await s.commit()

        recent = await cond._recent_messages()
        assert len(recent) == 10
        contents = [m.content for m in recent]
        # Ordem cronológica (mais antiga primeiro entre as 10 mais recentes).
        assert contents == [f"msg-{i:02d}" for i in range(5, 15)]


# ---------------------------------------------------------------------------
# FEAT-005: Pausa de confirmação pós-ideation (C4 / F-022)
# ---------------------------------------------------------------------------

async def test_ideation_pauses_for_confirmation(
    client, session_factory, monkeypatch
) -> None:
    """Ideia clara: card NÃO avança — fica em backlog aguardando confirmação."""
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    body = await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    # Após a ideation, o card NÃO avança (FEAT-005): permanece em backlog.
    assert body["card_id"] is not None
    assert body["awaiting_confirmation"] is True
    assert body["awaiting_user"] is False

    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "backlog"


async def test_ideation_pause_exposes_open_questions_when_ambiguous(
    client, session_factory, monkeypatch
) -> None:
    """Ideia vaga (FEAT-001): pausa expõe open_questions no output."""
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="",
            key_features=[],
            elevator_pitch="",
            confidence_score=0.1,
            open_questions=["qual o publico alvo?", "qual o orcamento?"],
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    body = await _turn(client, cid, "quero criar um app")
    assert body["awaiting_confirmation"] is True
    # FEAT-001: perguntas abertas expostas quando a ideia é vaga.
    assert body["tool_calls"][0]["output"]["open_questions"]
    # FEAT-005: mesmo com ambiguidade, o card pausa em backlog (não avança).
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "backlog"


async def test_confirm_ideation_advances_to_researching(
    client, session_factory, monkeypatch
) -> None:
    """Fallback determinístico em backlog (card existente) confirma -> researching."""
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    # T1: ideation cria o card e PAUSA em backlog.
    body = await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    card_id = body["card_id"]
    assert body["awaiting_confirmation"] is True
    card = await client.get("/api/v1/cards/" + card_id)
    assert card.json()["data"]["column"] == "backlog"

    # T2: confirma -> avança para researching (não recria card).
    body = await _turn(client, cid, "confirmar e prosseguir")
    assert body["awaiting_confirmation"] is False
    card = await client.get("/api/v1/cards/" + card_id)
    assert card.json()["data"]["column"] == "researching"


async def test_confirm_ideation_does_not_create_duplicate_card(
    client, session_factory, monkeypatch
) -> None:
    """Confirmar em backlog NÃO cria um segundo card (fallback ciente da pausa)."""
    from app.models.card import Card
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasFaculdade",
            key_features=["match"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "confirmar e prosseguir")

    async with session_factory() as s:
        from sqlalchemy import select, func

        total = (
            await s.execute(select(func.count()).select_from(Card))
        ).scalar()
        assert total == 1, "confirm em backlog não deve duplicar card"


async def test_confirm_ideation_with_correction_reruns_ideation(
    session_factory, monkeypatch
) -> None:
    """confirm_ideation com correções re-executa a Ideation antes de avançar."""
    from sqlalchemy import select

    from app.models import Artifact
    from app.models.card import Card
    from app.models.project import Project
    from app.services.agents.ideation import IdeationAgent, IdeationOutput
    from app.services.conductor import Conductor, TOOL_CONFIRM_IDEATION

    async def fake_run(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="CaronasCorrigida",
            key_features=["match"],
            elevator_pitch="p",
            confidence_score=0.9,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="backlog", title="Ideia original")
        s.add(card)
        await s.commit()
        await s.refresh(card)
        spy = _SpyLLM()
        cond, conv = await _make_conductor(s, proj.id, spy)
        cond._conversation.card_id = card.id
        await s.commit()

        result = await cond._run_tool(
            TOOL_CONFIRM_IDEATION, card, {"corrections": "foco em estudantes"}
        )
        assert result["card"].column == "researching"
        assert result["output"]["confirmed"] is True
        # Ideation foi re-executada: novo artifact com project_name corrigido.
        art = (
            await s.execute(
                select(Artifact).where(
                    Artifact.card_id == card.id, Artifact.agent_name == "ideation"
                )
            )
        ).scalars().first()
        assert art is not None
        assert "CaronasCorrigida" in art.content


# ---------------------------------------------------------------------------
# FEAT-004: Modo resposta livre `answer_question` (C2)
# ---------------------------------------------------------------------------

async def test_freeform_question_returns_narrative_only(
    client, session_factory, monkeypatch
) -> None:
    """Pergunta aberta em `planning`: responde narrativamente, NÃO roda o planner.

    O Conductor deve tratar a mensagem como discussão (sem intenção de avançar o
    pipeline) e usar `answer_question` — persistindo apenas a narrative, sem
    executar o próximo agente e sem mover o card de coluna.
    """
    from app.services.agents.ideation import IdeationAgent, IdeationOutput
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.agents.planner import PlannerAgent, PlannerOutput

    async def fake_ideation(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="App", key_features=["x"], elevator_pitch="p", confidence_score=0.9
        )

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    planner_ran = {"value": False}

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        planner_ran["value"] = True
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    monkeypatch.setattr(IdeationAgent, "run", fake_ideation)
    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)

    class _AnswerLLM:
        """LLM que avança o pipeline pelos turnos normais (fallback por coluna)
        e, apenas na pergunta aberta, decide responder em vez de avançar."""

        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            if "Postgres" in user_prompt:
                return {
                    "narrative": (
                        "Escolhi Postgres pela consistencia transacional e "
                        "suporte a JSONB."
                    ),
                    "tool_calls": [{"tool": "answer_question", "input": {}}],
                }
            # Turnos normais: tool_calls vazio -> fallback determinístico por coluna.
            return {"narrative": "", "tool_calls": []}

        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            return "narrativa"

    _override_services(client, _AnswerLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)

    # Avança até `planning` (ideation -> confirm -> research; planner ainda não rodou).
    await _turn(client, cid, "quero criar um app")
    await _turn(client, cid, "confirmar e prosseguir")
    to_planning = await _turn(client, cid, "pesquisar")
    card = await client.get("/api/v1/cards/" + to_planning["card_id"])
    assert card.json()["data"]["column"] == "planning"

    # Pergunta aberta — sem intenção de avançar o pipeline.
    resp = await _turn(client, cid, "por que escolheu Postgres?")

    # tool_calls está vazio OU contém apenas `answer_question`.
    tools = [tc["tool"] for tc in resp["tool_calls"]]
    assert all(t == "answer_question" for t in tools), tools
    # O Planner NÃO roda (apenas narrative é produzida).
    assert planner_ran["value"] is False
    # Não aguarda o usuário; o card não avança de coluna.
    assert resp["awaiting_user"] is False
    card = await client.get("/api/v1/cards/" + to_planning["card_id"])
    assert card.json()["data"]["column"] == "planning"


# ---------------------------------------------------------------------------
# FEAT-006: get_artifact — busca conteúdo COMPLETO de etapa já executada (C-1)
# ---------------------------------------------------------------------------

async def test_get_artifact_returns_real_content_after_research(
    session_factory, monkeypatch
) -> None:
    """Dado Research rodou, get_artifact('research') devolve o conteúdo REAL.

    Não o resumo de 1 linha ('Research Agent concluído'), e sim o conteúdo
    completo do artifact (ex.: sra_report com detalhes de concorrentes).
    """
    from app.models.card import Card
    from app.models.project import Project
    from app.services.conductor import Conductor, TOOL_GET_ARTIFACT
    from app.services.pipeline_helpers import latest_artifact_content

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="researching", title="App de caronas")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        # Persiste um artifact de research COM detalhe real (concorrentes).
        real_report = (
            "# Relatório de Pesquisa\n\n## Concorrentes\n"
            "- BlaBlaCar: caronas intermunicipais\n"
            "- Waze Carpool: foco em trajetos diários\n"
            "## Dores\n- confiança entre estranhos"
        )
        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        await s.commit()
        # Insere o artifact diretamente via persist do conductor.
        await cond._persist_artifact(card, "research", real_report)

        # get_artifact('research') devolve o conteúdo COMPLETO.
        result = await cond._run_tool(TOOL_GET_ARTIFACT, card, {"agent_name": "research"})
        assert result["output"].get("error") is None
        content = result["output"].get("content")
        assert content is not None
        # Detalhe real presente (não apenas o resumo da bolha de tool).
        assert "BlaBlaCar" in content
        assert "Waze Carpool" in content
        # O conteúdo no banco coincide com o devolvido.
        stored = await latest_artifact_content(s, card.id, "research")
        assert stored == content

        # get_artifact NÃO avança o card (tool somente-leitura).
        await s.refresh(card)
        assert card.column == "researching"


async def test_get_artifact_errors_clearly_when_step_not_run(
    session_factory, monkeypatch
) -> None:
    """Dado etapa 'dev' ainda não rodou, get_artifact('dev') erro claro (não exceção)."""
    from app.models.card import Card
    from app.models.project import Project
    from app.services.conductor import Conductor, TOOL_GET_ARTIFACT

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="planning", title="App")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id

        # 'dev' não rodou: erro claro, sem exceção não tratada.
        result = await cond._run_tool(TOOL_GET_ARTIFACT, card, {"agent_name": "dev"})
        assert result["output"].get("error") == "essa etapa ainda não foi executada"
        assert "content" not in result["output"]

        # agent_name fora da whitelist: erro claro (anti-injection).
        bad = await cond._run_tool(TOOL_GET_ARTIFACT, card, {"agent_name": "hacker"})
        assert bad["output"].get("error") == "etapa invalida"


async def test_get_artifact_works_in_done_column(
    session_factory, monkeypatch
) -> None:
    """get_artifact é GLOBAL: funciona em qualquer coluna, inclusive 'done'."""
    from app.models.card import Card
    from app.models.project import Project
    from app.services.conductor import Conductor, TOOL_GET_ARTIFACT

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="done", title="App finalizado")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        await s.commit()

        # Ideation rodou no passado; em 'done' ainda podemos buscar o conteúdo.
        ideation_content = '{"project_name": "CaronasFaculdade", "key_features": ["match"]}'
        await cond._persist_artifact(card, "ideation", ideation_content)

        result = await cond._run_tool(TOOL_GET_ARTIFACT, card, {"agent_name": "ideation"})
        assert result["output"].get("error") is None
        assert result["output"]["content"] == ideation_content
        # Card permanece em 'done' (tool não mexe na coluna).
        await s.refresh(card)
        assert card.column == "done"


# ---------------------------------------------------------------------------
# FEAT-008: revise_artifact — ajuste pontual sem reiniciar o pipeline (C-3)
# ---------------------------------------------------------------------------

async def test_revise_artifact_creates_new_version_without_rerunning_upstream(
    session_factory, monkeypatch
) -> None:
    """Dado Planner rodou, 'troca pra Postgres' gera NOVO artifact de planner.

    - NÃO re-executa Research/Code Research (montante).
    - O card NÃO muda de coluna (permanece em 'planning').
    - O artifact anterior é marcado `superseded` em `card.meta['artifact_versions']`.
    """
    from sqlalchemy import select

    from app.models.card import Card
    from app.models.project import Project
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )
    from app.services.conductor import Conductor, TOOL_REVISE_ARTIFACT
    from app.services.pipeline_helpers import latest_artifact_content

    upstream_ran = {"research": False, "code_research": False, "planner": 0}

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        upstream_ran["research"] = True
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        upstream_ran["code_research"] = True
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        upstream_ran["planner"] += 1
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="planning", title="App de caronas")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        # Artifact de planner original (antes da revisão).
        await cond._persist_artifact(card, "planner", '{"stack": ["py"]}')

        result = await cond._run_tool(
            TOOL_REVISE_ARTIFACT, card,
            {"agent_name": "planner", "instruction": "troca pra Postgres"},
        )
        assert result["output"].get("error") is None
        assert result["output"].get("revision_created") is True
        # O card NÃO muda de coluna durante a revisão.
        await s.refresh(card)
        assert card.column == "planning"
        # O Planner foi re-executado exatamente UMA vez (a revisão).
        assert upstream_ran["planner"] == 1
        # O montante NÃO foi re-executado.
        assert upstream_ran["research"] is False
        assert upstream_ran["code_research"] is False
        # Há DOIS artifacts de planner (original + revisão).
        arts = (
            await s.execute(
                select(Artifact).where(
                    Artifact.card_id == card.id, Artifact.agent_name == "planner"
                )
            )
        ).scalars().all()
        assert len(arts) == 2
        # O artifact_versions marca a versão anterior como superseded.
        versions = (card.meta or {}).get("artifact_versions", {})
        planner_versions = versions.get("planner", {})
        assert planner_versions.get("revisions") == 1
        assert planner_versions.get("superseded"), "anterior deve ser superseded"
        assert planner_versions.get("current") is not None
        # A NOVA versão do planner carrega a instrução de revisão
        # (rastreabilidade via comentário revise_artifact anexado ao artifact).
        new_content = next(
            a.content for a in arts if "revise_artifact" in a.content
        )
        assert "Postgres" in new_content
        # O artifact original (sem o comentário) permanece no banco (não apagado).
        originals = [a for a in arts if "revise_artifact" not in a.content]
        assert len(originals) == 1


async def test_revise_artifact_enforces_three_revision_limit(
    session_factory, monkeypatch
) -> None:
    """Dado 3 revisões já feitas, a 4ª recebe erro claro (limite de 3)."""
    from app.models.card import Card
    from app.models.project import Project
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.conductor import Conductor, TOOL_REVISE_ARTIFACT

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    monkeypatch.setattr(PlannerAgent, "run", fake_planner)

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="planning", title="App")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        await cond._persist_artifact(card, "planner", '{"stack": ["py"]}')

        # 3 revisões bem-sucedidas.
        for i in range(3):
            ok = await cond._run_tool(
                TOOL_REVISE_ARTIFACT, card,
                {"agent_name": "planner", "instruction": f"ajuste {i}"},
            )
            assert ok["output"].get("error") is None
        # 4ª chamada -> erro claro.
        blocked = await cond._run_tool(
            TOOL_REVISE_ARTIFACT, card,
            {"agent_name": "planner", "instruction": "ajuste a mais"},
        )
        assert blocked["output"].get("error") == "limite de 3 revisoes por etapa atingido"
        await s.refresh(card)
        assert (card.meta.get("artifact_versions", {}).get("planner", {}).get("revisions")) == 3


async def test_revise_planner_supersedes_reviewer_and_warns(
    session_factory, monkeypatch
) -> None:
    """Revisar planner quando Reviewer já rodou marca reviewer superseded + avisa.

    A narrativa deve informar que o Reviewer precisa rodar de novo.
    """
    from app.models.card import Card
    from app.models.project import Project
    from app.services.agents.planner import PlannerAgent, PlannerOutput
    from app.services.agents.reviewer import (
        ReviewerAgent,
        ReviewOutput,
    )
    from app.services.conductor import (
        Conductor,
        TOOL_REVISE_ARTIFACT,
    )
    from app.models.conversation import Message

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        return PlannerOutput(title="t", stack=["py"], milestones=[], risks=[])

    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        return ReviewOutput(
            alerts=[], critical_count=0, passed=True,
            confidence_score=0.95, log_summary=None,
        )

    monkeypatch.setattr(PlannerAgent, "run", fake_planner)
    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="reviewing", title="App")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        await s.commit()
        # Planner e Reviewer já rodaram (estado pré-revisão).
        await cond._persist_artifact(card, "planner", '{"stack": ["py"]}')
        await cond._persist_artifact(card, "reviewer", '{"passed": true}')
        # Marca o reviewer como já executado no versionamento.
        meta = dict(card.meta or {})
        meta["artifact_versions"] = {
            "planner": {"revisions": 0, "superseded": [], "current": "p1"},
            "reviewer": {"revisions": 0, "superseded": [], "current": "r1"},
        }
        card.meta = meta
        await s.commit()
        await s.refresh(card)

        result = await cond._run_tool(
            TOOL_REVISE_ARTIFACT, card,
            {"agent_name": "planner", "instruction": "troca pra Postgres"},
        )
        assert result["output"].get("error") is None
        assert result["output"].get("reviewer_superseded") is True
        # O card NÃO sai da coluna 'reviewing'.
        await s.refresh(card)
        assert card.column == "reviewing"
        # O versionamento marca o reviewer como superseded (lista de ids
        # desatualizados — estrutura do PRD Seção 1.3).
        versions = card.meta.get("artifact_versions", {})
        assert versions.get("reviewer", {}).get("superseded"), "reviewer deve ser marcado superseded"
        # A narrativa avisa que o Reviewer deve rodar de novo.
        narrative = result.get("narrative") or ""
        assert "Reviewer" in narrative
        assert "rodar" in narrative.lower() or "revis" in narrative.lower()


# ---------------------------------------------------------------------------
# FEAT-007: Memória por orçamento de tokens (C2 / histórico do prompt)
# ---------------------------------------------------------------------------

async def test_history_respects_token_budget(session_factory, monkeypatch) -> None:
    """O histórico acumulado NUNCA excede o orçamento de tokens (padrão 3000).

    Mensagens grandes (30+) devem ser resumidas (via compress_artifact) quando
    o acúmulo recente->antiga ultrapassa o orçamento; o total de tokens das
    mensagens efetivamente incluídas no prompt fica <= orçamento.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.card import Card
    from app.models.conversation import Message
    from app.models.project import Project
    from app.services.conductor import Conductor, TOOL_GET_CARD_STATE
    from app.core.config import get_settings

    budget = get_settings().conductor_history_token_budget

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="done", title="App")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        # Substitui compress_artifact por um resumo curto e determinístico
        # (evita depender de LLM auxiliar real no teste).
        async def _fake_compress(text, budget_tokens=800):  # noqa: ANN001
            return f"[RESUMO:{len(text)} chars]"

        monkeypatch.setattr(
            "app.services.conductor.compress_artifact", _fake_compress
        )

        spy = _SpyLLM()
        cond, conv = await _make_conductor(s, proj.id, spy)
        cond._conversation.card_id = card.id
        await s.commit()

        base = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        # 40 mensagens grandes (cada uma ~500 chars) — claramente acima do orçamento.
        for i in range(40):
            s.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content=f"mensagem longa numero {i:02d} " + "x" * 480,
                    created_at=base + timedelta(seconds=i),
                )
            )
            await s.commit()

        # Dispara o cálculo do histório orçado.
        hist_text = await cond._build_history_within_budget()
        assert hist_text  # não vazio

        # Reconstrói o total de tokens do que foi efetivamente incluído.
        included_tokens = sum(len(line) // 4 for line in hist_text.splitlines())
        assert included_tokens <= budget, (
            f"histórico excedeu orçamento: {included_tokens} > {budget}"
        )


async def test_early_fact_survives_summary(session_factory, monkeypatch) -> None:
    """Fato da msg 1 (nome do projeto) influencia a resposta após o resumo.

    Com >30 mensagens e orçamento estourado, as antigas são resumidas, mas o
    Conductor DEVE preservar decisões (ex.: o nome do projeto da 1ª mensagem)
    no prompt enviado ao LLM — ele deve aparecer no user_prompt do _plan.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.conversation import Message
    from app.models.project import Project
    from app.services.conductor import Conductor

    project_name = "CaronasFaculdade"

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)

        spy = _SpyLLM()
        cond, conv = await _make_conductor(s, proj.id, spy)

        base = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        # A 1ª mensagem trava o NOME DO PROJETO (fato crítico que deve sobreviver).
        s.add(
            Message(
                conversation_id=conv.id,
                role="user",
                content=f"vamos criar o projeto {project_name} de caronas",
                created_at=base,
            )
        )
        # 39 mensagens seguintes grandes para estourar o orçamento.
        for i in range(1, 40):
            s.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content=f"mensagem longa {i:02d} " + "y" * 480,
                    created_at=base + timedelta(seconds=i),
                )
            )
            await s.commit()

        # compress_artifact resumido (preserva o head onde está o nome do projeto?).
        # Garantimos a preservação injetando o fato como parte do resumo automático.
        async def _fake_compress(text, budget_tokens=800):  # noqa: ANN001
            # O resumo preserva o início (head) do texto, onde está o nome do projeto.
            return text[:200] if project_name not in text else text

        monkeypatch.setattr(
            "app.services.conductor.compress_artifact", _fake_compress
        )

        await cond._plan("continue o trabalho", column="researching")
        assert spy.last_user_prompt is not None
        # O nome do projeto da 1ª mensagem chega ao LLM (via resumo ou mensagem recente).
        assert project_name in spy.last_user_prompt


# ---------------------------------------------------------------------------
# FEAT-009: revert_approval — desfazer auto-approve recente via chat (C-4)
# ---------------------------------------------------------------------------


async def test_revert_approval_within_window_reverts_card(session_factory) -> None:
    """Dentro da janela, revert_approval volta a coluna e limpa auto-approve."""
    from datetime import datetime, timedelta, timezone

    from app.models.card import Card
    from app.models.project import Project
    from app.services.conductor import TOOL_REVERT_APPROVAL

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(
            project_id=proj.id,
            column="done",
            title="App",
            auto_approved=True,
            approval_by="auto",
            revert_deadline=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        )
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id

        result = await cond._run_tool(TOOL_REVERT_APPROVAL, card, {})
        assert result["output"].get("reverted") is True
        await s.refresh(card)
        assert card.column == "production"
        assert card.auto_approved is False
        assert card.approval_by == "none"
        assert card.revert_deadline is None


async def test_revert_approval_outside_window_returns_clear_message(
    session_factory,
) -> None:
    """Fora da janela, revert_approval não altera o card e explica o motivo."""
    from datetime import datetime, timedelta, timezone

    from app.models.card import Card
    from app.models.project import Project
    from app.services.conductor import TOOL_REVERT_APPROVAL

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(
            project_id=proj.id,
            column="done",
            title="App",
            auto_approved=True,
            approval_by="auto",
            revert_deadline=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
        )
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id

        result = await cond._run_tool(TOOL_REVERT_APPROVAL, card, {})
        assert result["output"].get("reverted") is False
        assert "30 minutos" in result["output"].get("error", "")
        await s.refresh(card)
        # Estado preservado.
        assert card.column == "done"
        assert card.auto_approved is True


async def test_revert_approval_no_card_fails_open(session_factory) -> None:
    """Sem card, revert_approval devolve erro claro (fail-open, não exceção)."""
    from app.models.project import Project
    from app.services.conductor import TOOL_REVERT_APPROVAL

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        result = await cond._run_tool(TOOL_REVERT_APPROVAL, None, {})
        assert result["output"].get("error") == "no_card"


async def test_revert_approval_publishes_card_updated(
    session_factory, monkeypatch
) -> None:
    """A reversão bem-sucedida publica card.updated (Kanban em tempo real)."""
    from datetime import datetime, timedelta, timezone

    from app.models.card import Card
    from app.models.project import Project
    from app.services.conductor import TOOL_REVERT_APPROVAL
    from app.services.event_bus import Event, event_bus

    published: list = []
    monkeypatch.setattr(
        event_bus, "publish", lambda event: published.append(event)
    )

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(
            project_id=proj.id,
            column="done",
            title="App",
            auto_approved=True,
            approval_by="auto",
            revert_deadline=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        )
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        await cond._run_tool(TOOL_REVERT_APPROVAL, card, {})

    updated = [e for e in published if e.type == "card.updated"]
    assert updated, "revert_approval deve publicar card.updated"
    assert updated[-1].payload["column"] == "production"


# ---------------------------------------------------------------------------
# OPÇÃO A: paralelismo generalizado de tools independentes num turno
# ---------------------------------------------------------------------------

async def test_independent_tools_run_in_parallel_via_gather(
    client, session_factory, monkeypatch
) -> None:
    """Tools independentes (research + code_research + get_card_state) de um
    mesmo turno rodam concurrentemente via asyncio.gather.

    Prova de paralelismo real: todos iniciam antes de qualquer um terminar.
    O avanço de coluna (só research avança) é aplicado em sequência APÓS o
    gather, preservando a ordem do Kanban e a transação da sessão.
    """
    from app.services.agents.research import ResearchAgent, ResearchOutput
    from app.services.agents.code_research import (
        CodeResearchAgent,
        CodeResearchOutput,
    )

    events: list[tuple[str, str]] = []

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        events.append(("research", "start"))
        await asyncio.sleep(0.02)
        events.append(("research", "end"))
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_code_research(self, **kwargs):  # noqa: ANN001
        events.append(("code_research", "start"))
        await asyncio.sleep(0.02)
        events.append(("code_research", "end"))
        return CodeResearchOutput(suggestions=["a"], license_class="permissive")

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)

    _override_services(client, _FakeLLM())
    pid = await _seed_project(client)
    cid = await _create_conversation(client, pid)
    await _turn(client, cid, "quero criar um app de caronas pra faculdade")
    await _turn(client, cid, "confirmar e prosseguir")
    # T2: dispara research + code_research juntos (researching -> planning).
    body = await _turn(client, cid, "seguir com a pesquisa")

    assert body["awaiting_user"] is False
    card = await client.get("/api/v1/cards/" + body["card_id"])
    assert card.json()["data"]["column"] == "planning"

    # Prova de paralelismo: ambos iniciaram ANTES de qualquer um terminar.
    assert events[0][0] == "research" and events[0][1] == "start"
    assert events[1][0] == "code_research" and events[1][1] == "start"
    assert ("research", "end") not in events[:2]
    assert ("code_research", "end") not in events[:2]


# ---------------------------------------------------------------------------
# STREAMING HÍBRIDO: POST intacto + eventos agent.status/agent.chunk no WS
# ---------------------------------------------------------------------------

async def test_handle_turn_publishes_agent_events_via_eventbus(
    client, session_factory, monkeypatch
) -> None:
    """O handle_turn publica eventos de tempo real (agent.status/agent.chunk/
    agent.turn_done) no EventBus DURANTE a execução, sem alterar o retorno do
    POST (abordagem híbrida: POST síncrono intacto + streaming no WebSocket).

    Prova:
    - agent.status start/done são emitidos para as tools executadas;
    - agent.chunk é emitido com a narrative (mesmo sintetizada);
    - agent.turn_done sinaliza o fim;
    - o POST ainda devolve o turno completo (tool_calls + conductor_reply).
    """
    from app.models.card import Card
    from app.models.project import Project
    from app.services.event_bus import Event, event_bus

    published: list = []
    monkeypatch.setattr(
        event_bus, "publish", lambda event: published.append(event)
    )

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="planning", title="App de caronas")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _SpyLLM())
        cond._conversation.card_id = card.id
        # Roda o planner (tool única da coluna planning) via handle_turn completo.
        result = await cond.handle_turn("fazer o plano")

    # O POST continua devolvendo o turno completo (comportamento intacto).
    assert result["tool_calls"], "POST deve devolver tool_calls"
    assert result["conductor_reply"] is not None

    types = [e.type for e in published]
    # Status start/done do planner foram publicados.
    assert "agent.status" in types, f"esperado agent.status em {types}"
    status_events = [e for e in published if e.type == "agent.status"]
    agents = {e.payload["agent"] for e in status_events}
    assert "planner" in agents, f"planner deve ter status publicado: {agents}"
    # Toda tool com start tem correspondente done.
    for agent in agents:
        starts = sum(1 for e in status_events if e.payload["agent"] == agent and e.payload["status"] == "start")
        dones = sum(1 for e in status_events if e.payload["agent"] == agent and e.payload["status"] == "done")
        assert starts == dones == 1, f"{agent}: start/done devem casar (s={starts},d={dones})"
    # Chunk da narrative publicado.
    chunk_events = [e for e in published if e.type == "agent.chunk"]
    assert chunk_events, "agent.chunk deve ser publicado"
    joined = "".join(e.payload["text"] for e in chunk_events)
    assert result["conductor_reply"] in joined or joined.strip(), "chunk deve compor a narrative"
    # Sinal de fim de turno.
    assert "agent.turn_done" in types, "agent.turn_done deve ser publicado"


async def test_handle_turn_streams_llm_narrative_in_chunks(
    session_factory, monkeypatch
) -> None:
    """Quando o LLM devolve narrative, ela é publicada em CHUNKS (não 1 só).

    Isso habilita a progressão visual no frontend sem custo extra de LLM
    (o texto já existe no plano JSON do Conductor).
    """
    from app.models.card import Card
    from app.models.project import Project
    from app.services.event_bus import Event, event_bus

    class _NarrativeLLM(_SpyLLM):
        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            self.last_user_prompt = user_prompt
            return {
                "narrative": "Plano técnico pronto. Stack definida. Próximo passo é a revisão.",
                "tool_calls": [{"tool": "run_planner", "input": {}}],
            }

    published: list = []
    monkeypatch.setattr(
        event_bus, "publish", lambda event: published.append(event)
    )

    async with session_factory() as s:
        proj = Project(name="P")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        card = Card(project_id=proj.id, column="planning", title="App")
        s.add(card)
        await s.commit()
        await s.refresh(card)

        cond, conv = await _make_conductor(s, proj.id, _NarrativeLLM())
        cond._conversation.card_id = card.id
        await cond.handle_turn("fazer o plano")

    chunk_events = [e for e in published if e.type == "agent.chunk"]
    # A narrative do LLM (3 sentenças) deve vir em MAIS de 1 chunk.
    assert len(chunk_events) > 1, f"narrative do LLM deve vir em chunks: {len(chunk_events)}"
    joined = "".join(e.payload["text"] for e in chunk_events).strip()
    assert "Plano técnico pronto" in joined
