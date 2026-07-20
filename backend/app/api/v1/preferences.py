"""API de UserPreferences (F-010) — perfil de preferências aprendido.

Regra: só é 'applied' (usado nos prompts) quando confidence_count >= 2,
evitando overfitting em um único evento.

FEAT-001 (P0, IDOR): todas as rotas usam o usuario autenticado
(Depends(get_current_user)) como dono. O user_id NUNCA vem do path — assim um
usuario logado so pode ler/escrever SUAS proprias preferencias (OWASP API1:
Broken Object Level Authorization).
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_request_id
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


@router.post(
    "/{user_id}/preferences", response_model=None, status_code=status.HTTP_201_CREATED
)
async def reinforce_preference(
    user_id: str,
    body: PreferenceCreate,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # O user_id do path e IGNORADO por seguranca (FEAT-001): a preferencia e
    # sempre criada para o usuario autenticado, nunca para um terceiro informado
    # no path. Assim A POST /users/{B}/preferences cria para A (anti-IDOR).
    existing = (
        await session.scalars(
            select(UserPreference).where(
                UserPreference.user_id == user.id,
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
            user_id=user.id,
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
    user_id: str,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _assert_owns_path(user, user_id)
    rows = (
        await session.scalars(
            select(UserPreference).where(UserPreference.user_id == user.id)
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
    user_id: str,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Grafo de preferências aprendidas (Fase D1 / F-010 §5).

    Exporta JSON {nodes, edges, stats} a partir da tabela ``user_preferences``
    para o frontend desenhar o grafo "Preferências Aprendidas".
    """
    _assert_owns_path(user, user_id)
    graph = await build_graph(session, user_id=user.id)
    return success_envelope(
        data=PreferenceGraphResponse(**graph).model_dump(mode="json"),
        request_id=request_id,
    )


@router.patch("/{user_id}/preferences/{preference_id}", response_model=None)
async def edit_preference(
    user_id: str,
    preference_id: str,
    body: PreferenceEdit,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Edita o valor de uma preferência (reescreve, mantém histórico de reforço)."""
    pref = await _require_owner(session, user, preference_id)
    pref = await mutate_preference(
        session, str(pref.id), "edit", value=body.value, user_id=user.id
    )
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


@router.delete("/{user_id}/preferences/{preference_id}", response_model=None)
async def archive_preference(
    user_id: str,
    preference_id: str,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove (arquiva recuperável) uma preferência — não apaga o histórico físico."""
    pref = await _require_owner(session, user, preference_id)
    pref = await mutate_preference(session, str(pref.id), "remove", user_id=user.id)
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


@router.post("/{user_id}/preferences/{preference_id}/restore", response_model=None)
async def restore_preference(
    user_id: str,
    preference_id: str,
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Restaura uma preferência arquivada (reverte o arquivamento)."""
    pref = await _require_owner(session, user, preference_id)
    pref = await mutate_preference(session, str(pref.id), "restore", user_id=user.id)
    data = PreferenceResponse.model_validate(pref).model_dump(mode="json")
    data["applied"] = pref.confidence_count >= APPLY_THRESHOLD
    return success_envelope(data=data, request_id=request_id)


def _assert_owns_path(user: User, user_id: str) -> None:
    """O user_id do path DEVE coincidir com o usuario autenticado.

    Levanta 404 (e nao 403) para nao vazar a existencia de recursos de terceiros.
    """
    if str(user.id) != str(user_id):
        raise NotFoundError("User", str(user_id))


async def _require_owner(
    session: AsyncSession, user: User, preference_id: str
) -> UserPreference:
    """Garante que a preferência existe e pertence ao usuario autenticado."""
    try:
        pref_uuid = UUID(str(preference_id))
    except (ValueError, AttributeError):
        raise NotFoundError("UserPreference", str(preference_id))
    pref = await session.get(UserPreference, pref_uuid)
    if pref is None:
        raise NotFoundError("UserPreference", str(preference_id))
    if pref.user_id != user.id:
        raise NotFoundError("UserPreference", str(preference_id))
    return pref
