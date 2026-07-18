"""Endpoint /conversations — Orquestração Conversacional (F-023 Conductor).

Expõe a criação de conversas e o loop de turnos do Conductor. Reusa as mesmas
dependências de serviço do /run (get_llm, get_sra, get_firecrawl, get_github,
get_sandbox). O Conductor avança o mesmo Card do Kanban, então o board reflete
o chat em tempo real.

Contrato (Plano F-023 §4):
  POST /conversations                      -> cria conversa (project_id)
  POST /conversations/{id}/messages        -> roda um turno do Conductor
  GET  /conversations/{id}/messages        -> histórico da conversa
"""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request

from app.api.v1.deps import (
    get_current_user,
    get_owned_conversation,
    get_request_id,
)
from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.responses import success_envelope
from app.models.conversation import Conversation, Message
from app.models.project import Project
from app.models.user import User
from app.schemas.conductor import (
    ConversationCreate,
    ConversationMessagesResponse,
    ConversationResponse,
    ConductorTurnRequest,
    ConductorTurnResponse,
    MessageResponse,
)
from app.services.conductor import Conductor
from app.services.deps import (
    get_firecrawl,
    get_github,
    get_llm,
    get_sandbox,
    get_sra,
    set_service_overrides,
)
from app.core.config import get_settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = get_logger("conversations_endpoint")


class _ReviseLLM:
    """LLM fake de validação E2E (apenas debug): força revise_artifact.

    Quando o prompt indica uma MUDANÇA (troca/muda/Postgres/stack/etc.),
    devolve tool_calls=[revise_artifact] para exercitar a FEAT-008 de ponta
    a ponta sem depender do LLM real (que poderia preferir run_planner).
    Para qualquer outra mensagem, devolve tool_calls vazio (fallback
    determinístico por coluna).
    """

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        lowered = user_prompt.lower()
        # FEAT-009: pedido explícito de desfazer -> força revert_approval.
        if any(
            k in lowered
            for k in ("desfaz", "desfazer", "reverte", "reverter", "volta o card")
        ):
            return {
                "narrative": "Vou desfazer a aprovação automática do card.",
                "tool_calls": [{"tool": "revert_approval", "input": {}}],
            }
        if any(k in lowered for k in ("troca", "muda", "postgres", "stack", "revise")):
            return {
                "narrative": "Vou revisar o plano com a mudança solicitada.",
                "tool_calls": [
                    {"tool": "revise_artifact", "input": {"agent_name": "planner"}}
                ],
            }
        return {"narrative": "", "tool_calls": []}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return "narrativa fake"


@router.post("/_override_llm", response_model=None)
async def override_llm(
    request: Request, request_id: str = Depends(get_request_id)
) -> dict:
    """Override de LLM para validação E2E (FEAT-008). Só em debug.

    Injeta um LLM fake que força revise_artifact em pedidos de mudança,
    tornando o E2E determinístico sem dependência do LLM real. Não exposto
    em produção (settings.debug=False).
    """
    if not get_settings().debug:
        raise NotFoundError("Endpoint", "_override_llm (debug only)")
    set_service_overrides(request, llm=_ReviseLLM())
    return success_envelope(data={"overridden": True}, request_id=request_id)


@router.post("/{conversation_id}/_seed_auto_approved", response_model=None)
async def seed_auto_approved_card(
    conversation_id: UUID,
    request: Request,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Semeia um card auto-aprovado ligado à conversa para o E2E do FEAT-009.

    Cria um card em 'done', com auto_approved=True e revert_deadline dentro da
    janela de 30 minutos, e o vincula à conversa. Permite validar o
    revert_approval pelo chat sem rodar o pipeline caro (LLM+MCP). Só em debug.
    """
    if not get_settings().debug:
        raise NotFoundError("Endpoint", "_seed_auto_approved (debug only)")

    from datetime import datetime, timedelta, timezone

    from app.models.card import Card
    from app.services.conductor import AUTO_APPROVE_REVERT_WINDOW_MIN

    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise NotFoundError("Conversation", str(conversation_id))

    card = Card(
        project_id=conv.project_id,
        column="done",
        title="Card auto-aprovado (E2E FEAT-009)",
        confidence_score=0.95,
        approval_by="auto",
        auto_approved=True,
        revert_deadline=datetime.now(tz=timezone.utc)
        + timedelta(minutes=AUTO_APPROVE_REVERT_WINDOW_MIN),
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)

    conv.card_id = card.id
    await session.commit()

    return success_envelope(
        data={
            "card_id": str(card.id),
            "column": card.column,
            "auto_approved": card.auto_approved,
        },
        request_id=request_id,
    )


def _to_conversation_response(c: Conversation) -> ConversationResponse:
    return ConversationResponse(id=c.id, project_id=c.project_id, card_id=c.card_id)


def _to_message_response(m: Message) -> MessageResponse:
    return MessageResponse(
        id=m.id,
        conversation_id=m.conversation_id,
        role=m.role,
        content=m.content,
        tool_name=m.tool_name,
        tool_input=m.tool_input,
        tool_output=m.tool_output,
    )


@router.post("", response_model=None)
async def create_conversation(
    payload: ConversationCreate,
    request_id: str = Depends(get_request_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm=Depends(get_llm),
    sra=Depends(get_sra),
    firecrawl=Depends(get_firecrawl),
    github=Depends(get_github),
    sandbox=Depends(get_sandbox),
) -> dict:
    # Valida que o project_id pertence ao usuário (IDOR).
    project = await session.get(Project, payload.project_id)
    if project is None or project.user_id != user.id:
        raise NotFoundError("Project", str(payload.project_id))
    conv = Conversation(project_id=project.id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    logger.info("conversation_created", conversation=str(conv.id))
    return success_envelope(
        data=_to_conversation_response(conv).model_dump(mode="json"),
        request_id=request_id,
    )


@router.post("/{conversation_id}/messages", response_model=None)
async def post_message(
    conv: Conversation = Depends(get_owned_conversation),
    payload: ConductorTurnRequest = Body(...),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    llm=Depends(get_llm),
    sra=Depends(get_sra),
    firecrawl=Depends(get_firecrawl),
    github=Depends(get_github),
    sandbox=Depends(get_sandbox),
) -> dict:
    conversation_id = conv.id

    conductor = Conductor(
        conversation=conv,
        session=session,
        llm=llm,
        sra=sra,
        firecrawl=firecrawl,
        github=github,
        sandbox=sandbox,
    )
    result = await conductor.handle_turn(payload.content)

    response = ConductorTurnResponse(
        conversation_id=conversation_id,
        conductor_reply=result["conductor_reply"],
        tool_calls=[
            {
                "tool": t.get("tool"),
                "input": t.get("input"),
                "output": t.get("output"),
            }
            for t in result["tool_calls"]
        ],
        card_id=result["card_id"],
        awaiting_user=result["awaiting_user"],
        awaiting_confirmation=result.get("awaiting_confirmation", False),
    )
    return success_envelope(
        data=response.model_dump(mode="json"), request_id=request_id
    )


@router.get("/{conversation_id}/messages", response_model=None)
async def list_messages(
    conv: Conversation = Depends(get_owned_conversation),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    messages = (await session.execute(stmt)).scalars().all()

    response = ConversationMessagesResponse(
        conversation=_to_conversation_response(conv),
        messages=[_to_message_response(m) for m in messages],
    )
    return success_envelope(
        data=response.model_dump(mode="json"), request_id=request_id
    )
