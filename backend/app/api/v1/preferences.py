"""API de UserPreferences (F-010) — perfil de preferências aprendido.

Regra: só é 'applied' (usado nos prompts) quando confidence_count >= 2,
evitando overfitting em um único evento.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.responses import success_envelope
from app.models.user import User
from app.models.user_preference import UserPreference
from app.schemas.preference import (
    PreferenceCreate,
    PreferenceEdit,
    PreferenceGraphResponse,
    PreferenceListResponse,
    PreferenceResponse,
)
from app.services.preference_graph import build_graph, mutate_preference

router = APIRouter(prefix="/users", tags=["preferences"])

APPLY_THRESHOLD = 2


@router.post("/{user_id}/preferences", response_model=None, status_code=status.HTTP_201_CREATED)
async def reinforce_preference(
    user_id: UUID,
    body: PreferenceCreate,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(User, user_id):
        raise NotFoundError("User", str(user_id))

    existing = (
        await session.scalars(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.attribute == body.attribute,
                UserPreference.value == body.value,
            )
        )
    ).first()

    now = datetime.now(tz=timezone.utc)
    if existing:
        existing.confidence_count += 1
        existing.last_reinforced_at = now
        pref = existing
    else:
        pref = UserPreference(
            user_id=user_id,
            attribute=body.attribute,
            value=body.value,
            confidence_count=1,
            last_reinforced_at=now,
        )
        session.add(pref)

    await session.commit()
    await session.refresh(pref)
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


@router.get("/{user_id}/preferences", response_model=None)
async def list_preferences(
    user_id: UUID,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(User, user_id):
        raise NotFoundError("User", str(user_id))
    rows = (
        await session.scalars(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
    ).all()
    items = []
    for r in rows:
        d = PreferenceResponse.model_validate(r).model_dump(mode="json")
        d["applied"] = r.confidence_count >= APPLY_THRESHOLD
        items.append(d)
    return success_envelope(
        data=PreferenceListResponse(items=items).model_dump()["items"],
        request_id=request_id,
    )


@router.get("/{user_id}/preferences/graph", response_model=None)
async def get_preference_graph(
    user_id: UUID,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Grafo de preferências aprendidas (Fase D1 / F-010 §5).

    Exporta JSON {nodes, edges, stats} a partir da tabela ``user_preferences``
    para o frontend desenhar o grafo "Preferências Aprendidas".
    """
    if not await session.get(User, user_id):
        raise NotFoundError("User", str(user_id))
    graph = await build_graph(session, user_id=user_id)
    return success_envelope(
        data=PreferenceGraphResponse(**graph).model_dump(mode="json"),
        request_id=request_id,
    )


@router.patch("/{user_id}/preferences/{preference_id}", response_model=None)
async def edit_preference(
    user_id: UUID,
    preference_id: UUID,
    body: PreferenceEdit,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Edita o valor de uma preferência (reescreve, mantém histórico de reforço)."""
    await _require_owner(session, user_id, preference_id)
    pref = await mutate_preference(
        session, str(preference_id), "edit", value=body.value
    )
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


@router.delete("/{user_id}/preferences/{preference_id}", response_model=None)
async def archive_preference(
    user_id: UUID,
    preference_id: UUID,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove (arquiva recuperável) uma preferência — não apaga o histórico físico."""
    await _require_owner(session, user_id, preference_id)
    pref = await mutate_preference(session, str(preference_id), "remove")
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


@router.post("/{user_id}/preferences/{preference_id}/restore", response_model=None)
async def restore_preference(
    user_id: UUID,
    preference_id: UUID,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Restaura uma preferência arquivada (reverte o arquivamento)."""
    await _require_owner(session, user_id, preference_id)
    pref = await mutate_preference(session, str(preference_id), "restore")
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


async def _require_owner(
    session: AsyncSession, user_id: UUID, preference_id: UUID
) -> UserPreference:
    """Garante que a preferência existe e pertence ao user_id informado."""
    pref = await session.get(UserPreference, preference_id)
    if pref is None:
        raise NotFoundError("UserPreference", str(preference_id))
    if pref.user_id != user_id:
        raise NotFoundError("UserPreference", str(preference_id))
    return pref
