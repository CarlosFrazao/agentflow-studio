"""Compartilhamento de sessão via URL (Item D do analise_omnigent.md).

Expõe o board Kanban de um projeto (cards agrupados por coluna) e as
execuções recentes em uma rota PÚBLICA, sem JWT — para que equipes
acompanhem o progresso remoto. Opcionalmente protegida por token de
acesso (quando o projeto define um share_token).

O WebSocket em /share/{project_id}/ws transmite atualizações em tempo real
(ver app/api/v1/share_ws.py), alimentado pelo EventBus.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_request_id
from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.responses import success_envelope
from app.models.card import Card
from app.models.execution import Execution
from app.models.project import Project

router = APIRouter(prefix="/share", tags=["share"])

# Colunas canônicas do pipeline (PRD F-001)
COLUMNS = ["backlog", "researching", "planning", "reviewing", "production", "done"]


def build_shared_board(project_id: str, cards: list, executions: list) -> dict:
    """Serializa o board de um projeto para exposição pública.

    `cards` e `executions` podem ser ORM ou objetos com atributos simples.
    Retorna colunas vazias para manter o shape estável no frontend.
    """
    columns: dict[str, list] = {col: [] for col in COLUMNS}
    for c in cards:
        col = getattr(c, "column", "backlog")
        if col not in columns:
            col = "backlog"
        columns[col].append(
            {
                "id": str(c.id),
                "title": getattr(c, "title", ""),
                "column": col,
                "meta": getattr(c, "meta", {}) or {},
            }
        )
    recent = [
        {
            "id": str(e.id),
            "card_id": str(e.card_id),
            "agent_name": e.agent_name,
            "status": e.status,
            "cost_usd": e.cost_usd,
        }
        for e in executions
    ]
    return {"project_id": str(project_id), "columns": columns, "recent_executions": recent}


@router.get("/{project_id}", response_model=None)
async def get_shared_board(
    project_id: UUID,
    request: Request,
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    project = await session.get(Project, project_id)
    if not project:
        raise NotFoundError("Project", str(project_id))
    cards = (
        await session.scalars(select(Card).where(Card.project_id == project_id))
    ).all()
    executions = (
        await session.scalars(
            select(Execution)
            .where(Execution.card_id.in_([c.id for c in cards]))
            .order_by(Execution.started_at.desc().nullslast())
            .limit(20)
        )
    ).all()
    board = build_shared_board(str(project_id), cards, executions)
    return success_envelope(data=board, request_id=request_id)
