"""Engine assíncrono e gerenciamento de sessão (SQLAlchemy 2.x + aiosqlite).

O schema é gerenciado por migrações versionadas do Alembic (ver alembic.ini /
alembic/). Em runtime, init_db() aplica `alembic upgrade head`. Para um banco
fresco em dev/teste, rode `alembic upgrade head` (não há create_all)."""

from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import asyncio

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("database")

settings = get_settings()


def _ensure_db_dir() -> None:
    """Garante que o diretório do arquivo SQLite exista (sqlite não cria pais)."""
    url = settings.database_url
    if url.startswith("sqlite") and ":///" in url:
        path = url.split("///", 1)[1]
        # remove query/fragment se houver
        path = path.split("?")[0].split("#")[0]
        parent = Path(path).parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session


async def init_db() -> None:
    """Aplica as migrações do Alembic (upgrade head).

    Não usa create_all: o schema é 100% versionado. Para um banco fresco em
    dev/teste, isto cria as tabelas a partir da migração inicial. Em produção
    (banco já existente), o banco deve ter sido `alembic stamp head` uma vez
    (ver handoff) — depois upgrade head é idempotente.
    """
    from alembic import command
    from alembic.config import Config

    _ensure_db_dir()
    # Resolve o alembic.ini relativo a este arquivo (backend/).
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))

    try:
        # Loop já ativo (FastAPI lifespan / Starlette TestClient): o Alembic
        # usa asyncio.run() internamente, o que collide com o loop corrente.
        # Rodamos o upgrade numa thread isolada (seu próprio loop) e aguardamos
        # sem bloquear o loop da aplicação.
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(executor, lambda: command.upgrade(cfg, "head"))
    except RuntimeError:
        # Sem loop em execução (CLI standalone: `alembic upgrade head`).
        command.upgrade(cfg, "head")

    logger.info("database_migrated", url=settings.database_url)


async def close_db() -> None:
    await engine.dispose()
    logger.info("database_closed")
