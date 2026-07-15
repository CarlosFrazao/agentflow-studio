"""API de Users — MVP single-tenant (sem auth). CRUD básico."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.api.v1.deps import get_request_id
from app.core.responses import success_envelope
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate, request_id: str = Depends(get_request_id), session: AsyncSession = Depends(get_session)
) -> dict:
    user = User(email=body.email, display_name=body.display_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return success_envelope(
        data=UserResponse.model_validate(user).model_dump(mode="json"),
        request_id=request_id,
    )


@router.get("/{user_id}", response_model=None)
async def get_user(
    user_id: UUID, request_id: str = Depends(get_request_id), session: AsyncSession = Depends(get_session)
) -> dict:
    user = await session.get(User, user_id)
    if not user:
        raise NotFoundError("User", str(user_id))
    return success_envelope(
        data=UserResponse.model_validate(user).model_dump(mode="json"),
        request_id=request_id,
    )
