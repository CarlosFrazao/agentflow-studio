"""API de Cards (Kanban) — CRUD + movimentação de coluna com envelope padronizado."""

from uuid import UUID
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import (
    ApprovalWindowExpiredError,
    NotFoundError,
    ValidationError,
)
from app.api.v1.deps import (
    get_current_user,
    get_owned_card,
    get_request_id,
)
from app.core.responses import paginated_envelope, success_envelope
from app.models.card import KANBAN_COLUMNS, Card
from app.models.project import Project
from app.models.user import User
from app.schemas.card import CardCreate, CardResponse, CardUpdate
from app.services.event_bus import Event, event_bus
from app.services.orchestrator import revert_auto_approval
from app.services.prompt_hydration import hydrate_prompt

router = APIRouter(prefix="/cards", tags=["cards"])


def _deep_merge_meta(base: dict, incoming: dict) -> dict:
    """Recursively merge ``incoming`` into ``base``, preserving nested sub-keys.

    Unlike ``dict.update``, nested dicts are merged key-by-key so a partial
    update (e.g. ``{"review_logs": {"x": 1}}``) does not clobber sibling keys
    already present in ``base``. Lists and scalars are replaced wholesale.
    """
    result: dict[str, Any] = dict(base)
    for key, value in incoming.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge_meta(existing, value)
        else:
            result[key] = value
    return result


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_card(
    body: CardCreate,
    request_id: str = Depends(get_request_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # FEAT-007 (B2-1): revalidação defense-in-depth de ownership. `Project.user_id`
    # é nullable (models/project.py:16) — um project órfão (user_id=None) NÃO
    # pode aceitar cards de qualquer usuário autenticado (escalada de tenant).
    # A comparação `project.user_id != user.id` cobre ambos os casos: inexistente
    # (project is None) e órfão (user_id is None != user.id), rejeitando com 422.
    project = await session.get(Project, body.project_id)
    if project is None or project.user_id != user.id:
        raise ValidationError("project_id invalido ou inexistente")
    # Item C: hidrata o título do usuário (PT informal -> EN técnico + regras).
    # llm=None mantém o caminho síncrono determinístico (zero I/O) neste
    # endpoint async — o LLMTranslator (asyncio.run) não pode rodar sob o loop
    # ativo do FastAPI; a tradução fluida via LLM fica para chamadores síncronos.
    meta = dict(body.meta or {})
    hydrated = hydrate_prompt(
        body.title, project_context={"name": project.name}, llm=None
    )
    if hydrated:
        meta["hydrated_prompt"] = hydrated
    # Security (FEAT-006): auto-approve fields are NEVER client-controlled.
    # A freshly created card must always start as not auto-approved so the
    # Human-in-the-Loop gate (POST /run) remains the only path that sets them.
    card = Card(
        project_id=body.project_id,
        title=body.title,
        column=body.column,
        order_index=body.order_index,
        confidence_score=body.confidence_score,
        approval_by="none",
        auto_approved=False,
        revert_deadline=None,
        meta=meta,
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    # Publica evento para o WebSocket de compartilhamento (Item D).
    event_bus.publish(
        Event(
            type="card.created",
            payload={
                "card_id": str(card.id),
                "project_id": str(card.project_id),
                "column": card.column,
            },
        )
    )
    return success_envelope(
        data=CardResponse.model_validate(card).model_dump(mode="json"),
        request_id=request_id,
    )


@router.get("", response_model=None)
async def list_cards(
    request_id: str = Depends(get_request_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project_id: UUID | None = Query(default=None),
    column: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> dict:
    # Valida que o project_id (se informado) pertence ao usuário.
    if project_id is not None:
        proj = await session.get(Project, project_id)
        if proj is None or proj.user_id != user.id:
            raise NotFoundError("Project", str(project_id))
    stmt = select(Card)
    if project_id is not None:
        stmt = stmt.where(Card.project_id == project_id)
    if column is not None:
        if column not in KANBAN_COLUMNS:
            raise ValidationError(f"coluna invalida: {column}")
        stmt = stmt.where(Card.column == column)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    offset = (page - 1) * per_page
    rows = (
        await session.scalars(
            stmt.offset(offset).limit(per_page).order_by(Card.order_index)
        )
    ).all()
    items = [CardResponse.model_validate(r).model_dump(mode="json") for r in rows]
    return paginated_envelope(
        data=items, total=total, page=page, per_page=per_page, request_id=request_id
    )


@router.get("/{card_id}", response_model=None)
async def get_card(
    card: Card = Depends(get_owned_card),
    request_id: str = Depends(get_request_id),
) -> dict:
    return success_envelope(
        data=CardResponse.model_validate(card).model_dump(mode="json"),
        request_id=request_id,
    )


@router.patch("/{card_id}", response_model=None)
async def update_card(
    card: Card = Depends(get_owned_card),
    body: CardUpdate = Body(...),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.title is not None:
        card.title = body.title
    if body.column is not None:
        if body.column not in KANBAN_COLUMNS:
            raise ValidationError(f"coluna invalida: {body.column}")
        card.column = body.column
    if body.order_index is not None:
        card.order_index = body.order_index
    if body.confidence_score is not None:
        card.confidence_score = body.confidence_score
    # NOTA: `approval_by`/`auto_approved` sao intencionalmente IGNORADOS aqui
    # (Audit BUG-006). So podem ser definidos via /run (auto-approve ADR-007)
    # ou /revert-approval. O schema CardUpdate nem expoe esses campos.
    if body.meta is not None:
        card.meta = _deep_merge_meta(card.meta or {}, body.meta)
    await session.commit()
    await session.refresh(card)
    return success_envelope(
        data=CardResponse.model_validate(card).model_dump(mode="json"),
        request_id=request_id,
    )


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card: Card = Depends(get_owned_card),
    session: AsyncSession = Depends(get_session),
) -> None:
    await session.delete(card)
    await session.commit()


@router.post("/{card_id}/revert-approval", response_model=None)
async def revert_approval(
    card: Card = Depends(get_owned_card),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Desfaz um auto-approve recente dentro da janela de reversão (FEAT-009).

    - Card já manual (``auto_approved is False``): idempotente — devolve 200
      ``{reverted: False}`` sem mover coluna nem publicar evento.
    - Card auto-aprovado dentro da janela: o helper ``revert_auto_approval``
      reverte, persiste, publica ``card.updated`` (WebSocket, tempo real) e
      devolve 200 ``{reverted: True}``.
    - Card auto-aprovado fora da janela: helper retorna False -> 400
      ``APPROVAL_WINDOW_EXPIRED`` (não altera o card).
    """
    if not card.auto_approved:
        return success_envelope(
            data={"card_id": str(card.id), "reverted": False},
            request_id=request_id,
        )
    reverted = revert_auto_approval(card)
    if not reverted:
        raise ApprovalWindowExpiredError()
    await session.commit()
    await session.refresh(card)
    # Publica card.updated para o WebSocket de compartilhamento (mesmo payload
    # que o Conductor emite — o share_ws filtra por project_id).
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
    return success_envelope(
        data={
            "card_id": str(card.id),
            "reverted": True,
            "column": card.column,
        },
        request_id=request_id,
    )
