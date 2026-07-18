"""Agregador de routers da API v1."""

from fastapi import APIRouter, Depends

from app.api.v1 import (
    agents,
    artifacts,
    auth,
    budget,
    cards,
    conversations,
    dashboard,
    health,
    metrics,
    preferences,
    projects,
    run,
    share,
    share_ws,
    snippets,
)
from app.api.v1.deps import get_current_user

router = APIRouter()
# Públicos: health + auth (registro/login).
router.include_router(health.router)
router.include_router(auth.router)
# Público: compartilhamento de sessão via URL (Item D).
router.include_router(share.router)
router.include_router(share_ws.router)
# Protegidos por JWT.
router.include_router(
    projects.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    cards.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    conversations.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    artifacts.router, dependencies=[Depends(get_current_user)]
)
router.include_router(run.router, dependencies=[Depends(get_current_user)])
router.include_router(
    snippets.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    preferences.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    budget.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    dashboard.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    metrics.router, dependencies=[Depends(get_current_user)]
)
router.include_router(
    agents.router, dependencies=[Depends(get_current_user)]
)
