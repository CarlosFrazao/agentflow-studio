"""WebSocket de compartilhamento em tempo real (Item D do analise_omnigent.md).

Transmite eventos do EventBus (cards movidos, executados, etc.) para todos
os clientes conectados em /share/{project_id}/ws, permitindo acompanhamento
remoto ao vivo do board.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.event_bus import Event, event_bus

router = APIRouter(prefix="/share", tags=["share-ws"])


@router.websocket("/{project_id}/ws")
async def share_ws(websocket: WebSocket, project_id: str) -> None:
    await websocket.accept()
    queue = event_bus.subscribe()
    try:
        # Avisa o cliente que a conexão está ativa
        await websocket.send_json({"type": "connected", "project_id": project_id})
        while True:
            event: Event = await queue.get()
            # Filtra por projeto quando o evento traz project_id no payload
            payload_project = event.payload.get("project_id")
            if payload_project is not None and payload_project != project_id:
                continue
            await websocket.send_json(
                {"type": event.type, "payload": event.payload}
            )
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)
