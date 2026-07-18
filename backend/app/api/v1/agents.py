"""API de Agentes declarativos (Item A do analise_omnigent.md).

Permite CRUD de definições de agentes (YAML/JSON) persistidas em disco e
espelhadas no SQLite. Segue o envelope padronizado da API.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.responses import success_envelope
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services import agent_definitions as svc

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=None)
async def list_agents(
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> dict:
    agents = await svc.list_agents(session)
    return success_envelope(
        data=[a.model_dump(mode="json") for a in agents], request_id=request_id
    )


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> dict:
    agent = await svc.create_agent(body, session)
    return success_envelope(data=agent.model_dump(mode="json"), request_id=request_id)


@router.get("/{name}", response_model=None)
async def get_agent(
    name: str,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> dict:
    agent = await svc.get_agent_by_name(name, session)
    if agent is None:
        raise NotFoundError("Agent", name)
    return success_envelope(data=agent.model_dump(mode="json"), request_id=request_id)


@router.put("/{name}", response_model=None)
async def update_agent(
    name: str,
    body: AgentUpdate,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> dict:
    agent = await svc.update_agent_by_name(name, body, session)
    if agent is None:
        raise NotFoundError("Agent", name)
    return success_envelope(data=agent.model_dump(mode="json"), request_id=request_id)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> None:
    await svc.delete_agent_by_name(name, session)
