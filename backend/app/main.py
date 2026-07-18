"""App factory do AgentFlow Studio (FastAPI)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import configure_logging, get_logger
from app.core.responses import error_envelope

logger = get_logger("app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover - wiring de ciclo de vida
    configure_logging()
    await init_db()
    logger.info("startup_complete")
    yield
    await close_db()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(v1_router, prefix=settings.api_prefix)
    _register_exception_handlers(app)
    _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    """Serve o build do frontend (Vite) em `/` (mesma origem da API).

    Permite que o app React consuma /api/v1 sem CORS.
    O diretório é opcional: se ausente, apenas a API é servida.

    Estratégia SPA: os assets estáticos (JS/CSS/imagens) ficam montados em `/`,
    e uma rota catch-all devolve index.html para qualquer caminho que NÃO seja
    /api/* — assim o roteamento no lado do cliente (ex.: /projects/:id) funciona
    sem 404. A rota catch-all é registrada ANTES do mount para não ser capturada
    pelo StaticFiles.
    """
    static_dir = settings.static_dir
    if not static_dir or not static_dir.exists():
        logger.info("static_dir_ausente", path=str(static_dir))
        return

    index_file = static_dir / "index.html"

    static_resolved = static_dir.resolve()

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str) -> Response:
        # /api/* é tratado pelos routers (nunca chega aqui por causa do prefixo).
        # Se o arquivo solicitado existir DENTRO do build, serve ele; senão, index.html.
        # Resolve o caminho e garante que continua dentro de static_dir para evitar
        # path traversal (ex.: /../../../backend/.env).
        candidate = (static_dir / full_path).resolve()
        if (
            full_path
            and candidate.is_relative_to(static_resolved)
            and candidate.is_file()
        ):
            return FileResponse(str(candidate))
        if index_file.exists():
            return FileResponse(str(index_file))
        raise NotFoundError("index.html do frontend ausente", "FRONTEND_NOT_BUILT")

    logger.info("static_spa_montado", path=str(static_dir))


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_envelope(exc.code, exc.message, request_id=""),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=error_envelope(exc.code, exc.message, request_id=""),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_envelope(
                "INTERNAL_ERROR", "Erro interno nao esperado", request_id=""
            ),
        )


app = create_app()
