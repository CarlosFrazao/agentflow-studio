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

from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.responses import success_envelope
from app.models.conversation import Conversation, Message
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
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = get_logger("conversations_endpoint")


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
    request: Request,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    llm=Depends(get_llm),
    sra=Depends(get_sra),
    firecrawl=Depends(get_firecrawl),
    github=Depends(get_github),
    sandbox=Depends(get_sandbox),
) -> dict:
    conv = Conversation(project_id=payload.project_id)
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
    conversation_id: UUID,
    payload: ConductorTurnRequest,
    request: Request,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    llm=Depends(get_llm),
    sra=Depends(get_sra),
    firecrawl=Depends(get_firecrawl),
    github=Depends(get_github),
    sandbox=Depends(get_sandbox),
) -> dict:
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise NotFoundError("Conversation", str(conversation_id))

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
    )
    return success_envelope(
        data=response.model_dump(mode="json"), request_id=request_id
    )


@router.get("/{conversation_id}/messages", response_model=None)
async def list_messages(
    conversation_id: UUID,
    request: Request,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise NotFoundError("Conversation", str(conversation_id))

    stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(
        Message.created_at.asc(), Message.id.asc()
    )
    messages = (await session.execute(stmt)).scalars().all()

    response = ConversationMessagesResponse(
        conversation=_to_conversation_response(conv),
        messages=[_to_message_response(m) for m in messages],
    )
    return success_envelope(
        data=response.model_dump(mode="json"), request_id=request_id
    )
