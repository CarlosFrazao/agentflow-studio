"""WebSocket de compartilhamento em tempo real (Item D do analise_omnigent.md).

Transmite eventos do EventBus (cards movidos, executados, etc.) para os
clientes conectados em /share/{project_id}/ws, permitindo acompanhamento
remoto ao vivo do board.

OWASP API1 (BOLA): o WebSocket exige o JWT do usuário (via query param
`token`, pois o protocolo WS não aceita headers Authorization) e valida que
o project_id pertence a esse usuário ANTES de aceitar/assinar a conexão.
Sem isso, qualquer cliente que soubesse um project_id alheio recebia os
eventos daquele board em tempo real (vazamento cross-project).
"""

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.models.project import Project
from app.models.user import User
from app.services.event_bus import Event, event_bus

logger = get_logger("share_ws")

router = APIRouter(prefix="/share", tags=["share-ws"])


async def _authenticate_ws(websocket: WebSocket, session: AsyncSession) -> User:
    """Autentica o WebSocket via JWT no query param `token` (OWASP API1).

    Levanta UnauthorizedError se ausente/inválido; NotFoundError se o
    project_id (passado via path) não pertencer ao usuário. O caller fecha
    a conexão com 1011 antes de propagar, já que o WS já foi aceito.
    """
    token = websocket.query_params.get("token")
    if not token:
        raise UnauthorizedError("token de acesso ausente no WebSocket")
    user_id = decode_access_token(token)
    if user_id is None:
        raise UnauthorizedError("token invalido ou expirado")
    user = await session.get(User, UUID(user_id))
    if user is None:
        raise UnauthorizedError("usuario nao encontrado")
    return user


async def _assert_project_owned(
    project_id: str, user: User, session: AsyncSession
) -> None:
    """404 (e nao 403) se o project_id nao pertencer ao usuario."""
    project = await session.get(Project, UUID(project_id))
    if project is None or project.user_id != user.id:
        raise NotFoundError("Project", project_id)


@router.websocket("/{project_id}/ws")
async def share_ws(
    websocket: WebSocket, project_id: str, conversation_id: str | None = None
) -> None:
    # Aceita cedo para poder devolver um código de fechamento com mensagem.
    await websocket.accept()
    # get_session() e um async generator (Depends); iteramos manualmente
    # pois o WebSocket nao suporta Depends para gerenciar o ciclo de vida.
    session_gen = get_session()
    session = await session_gen.__anext__()
    try:
        try:
            user = await _authenticate_ws(websocket, session)
            await _assert_project_owned(project_id, user, session)
        except (UnauthorizedError, NotFoundError) as exc:
            # 1011 = erro de servidor/sessão; usamos para sinalizar authz falhou.
            await websocket.close(code=1011, reason=str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - loga falha inesperada no WS
            logger.error("share_ws_auth_error", error=str(exc), type=type(exc).__name__)
            await websocket.close(code=1011, reason="erro interno de autenticacao")
            return
    finally:
        await session_gen.aclose()

    queue = event_bus.subscribe()
    try:
        # Avisa o cliente que a conexão está ativa
        await websocket.send_json({"type": "connected", "project_id": project_id})
        while True:
            event: Event = await queue.get()
            payload = event.payload
            # Filtra por projeto quando o evento traz project_id no payload
            payload_project = payload.get("project_id")
            if payload_project is not None and payload_project != project_id:
                continue
            # Filtro opcional por conversa (chat em tempo real): se o cliente
            # pediu ?conversation_id=X, só entrega eventos dessa conversa.
            if conversation_id is not None:
                payload_conv = payload.get("conversation_id")
                if payload_conv is not None and payload_conv != conversation_id:
                    continue
            await websocket.send_json(
                {"type": event.type, "payload": payload}
            )
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)
