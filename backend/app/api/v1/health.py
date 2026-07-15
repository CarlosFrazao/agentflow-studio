"""Endpoint de health check (usado pelo Docker healthcheck e pelo orquestrador)."""

from fastapi import APIRouter, Request, status

from app.core.responses import success_envelope

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health(request: Request) -> dict:
    request_id = request.headers.get("X-Request-ID", "health")
    return success_envelope(data={"status": "ok"}, request_id=request_id)
