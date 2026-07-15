"""API de Projects — CRUD com envelope padronizado."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.api.v1.deps import get_request_id
from app.core.responses import paginated_envelope, success_envelope
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, request_id: str = Depends(get_request_id), session: AsyncSession = Depends(get_session)
) -> dict:
    project = Project(name=body.name, description=body.description)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return success_envelope(
        data=ProjectResponse.model_validate(project).model_dump(mode="json"),
        request_id=request_id,
    )


@router.get("", response_model=None)
async def list_projects(
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    offset = (page - 1) * per_page
    total = await session.scalar(select(func.count()).select_from(Project)) or 0
    rows = (
        await session.scalars(
            select(Project).offset(offset).limit(per_page).order_by(Project.created_at)
        )
    ).all()
    items = [ProjectResponse.model_validate(r).model_dump(mode="json") for r in rows]
    return paginated_envelope(
        data=items, total=total, page=page, per_page=per_page, request_id=request_id
    )


@router.get("/{project_id}", response_model=None)
async def get_project(
    project_id: UUID, request_id: str = Depends(get_request_id), session: AsyncSession = Depends(get_session)
) -> dict:
    project = await session.get(Project, project_id)
    if not project:
        raise NotFoundError("Project", str(project_id))
    return success_envelope(
        data=ProjectResponse.model_validate(project).model_dump(mode="json"),
        request_id=request_id,
    )


@router.patch("/{project_id}", response_model=None)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    request_id: str = Depends(get_request_id),

    session: AsyncSession = Depends(get_session),
) -> dict:
    project = await session.get(Project, project_id)
    if not project:
        raise NotFoundError("Project", str(project_id))
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    await session.commit()
    await session.refresh(project)
    return success_envelope(
        data=ProjectResponse.model_validate(project).model_dump(mode="json"),
        request_id=request_id,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, session: AsyncSession = Depends(get_session)
) -> None:
    project = await session.get(Project, project_id)
    if not project:
        raise NotFoundError("Project", str(project_id))
    await session.delete(project)
    await session.commit()
