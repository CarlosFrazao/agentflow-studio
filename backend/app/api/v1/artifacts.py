"""API de Artifacts — saída dos agents anexada a um card."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import success_envelope
from app.models.artifact import ARTIFACT_TYPES, Artifact
from app.models.card import Card
from app.schemas.artifact import ArtifactCreate, ArtifactResponse

router = APIRouter(prefix="/cards", tags=["artifacts"])


@router.post("/{card_id}/artifacts", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    card_id: UUID,
    body: ArtifactCreate,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(Card, card_id):
        raise NotFoundError("Card", str(card_id))
    if body.type not in ARTIFACT_TYPES:
        raise ValidationError(f"tipo de artifact invalido: {body.type}")
    artifact = Artifact(
        card_id=card_id,
        agent_name=body.agent_name,
        type=body.type,
        content=body.content,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return success_envelope(
        data=ArtifactResponse.model_validate(artifact).model_dump(mode="json"),
        request_id=request_id,
    )


@router.get("/{card_id}/artifacts", response_model=None)
async def list_artifacts(
    card_id: UUID,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(Card, card_id):
        raise NotFoundError("Card", str(card_id))
    rows = (
        await session.scalars(
            select(Artifact).where(Artifact.card_id == card_id)
        )
    ).all()
    items = [ArtifactResponse.model_validate(r).model_dump(mode="json") for r in rows]
    return success_envelope(data=items, request_id=request_id)
