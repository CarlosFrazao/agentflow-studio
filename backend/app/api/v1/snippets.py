"""API de Snippets (F-009) — biblioteca de trechos com licença obrigatória."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.responses import paginated_envelope, success_envelope
from app.models.snippet import Snippet
from app.models.user import User
from app.schemas.snippet import SnippetCreate, SnippetResponse

router = APIRouter(prefix="/snippets", tags=["snippets"])


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_snippet(
    body: SnippetCreate,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(User, body.user_id):
        raise NotFoundError("User", str(body.user_id))
    snippet = Snippet(
        user_id=body.user_id,
        title=body.title,
        content=body.content,
        language=body.language,
        license=body.license,
        source_url=body.source_url,
    )
    session.add(snippet)
    await session.commit()
    await session.refresh(snippet)
    return success_envelope(
        data=SnippetResponse.model_validate(snippet).model_dump(mode="json"),
        request_id=request_id,
    )


@router.get("", response_model=None)
async def list_snippets(
    request: Request,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
    user_id: UUID | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    stmt = select(Snippet)
    if user_id is not None:
        stmt = stmt.where(Snippet.user_id == user_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    offset = (page - 1) * per_page
    rows = (
        await session.scalars(
            stmt.offset(offset).limit(per_page).order_by(Snippet.created_at.desc())
        )
    ).all()
    items = [SnippetResponse.model_validate(r).model_dump(mode="json") for r in rows]
    return paginated_envelope(
        data=items, total=total, page=page, per_page=per_page, request_id=request_id
    )
