"""Fixtures de teste: engine SQLite em memória + override de sessão no app.

Usa ASGITransport (sem lifespan) — logo init_db() no arquivo real não roda
durante os testes; o schema é criado no engine em memória deste fixture.

A guarda JWT (get_current_user) é REAL e fica ATIVA em todos os routers
protegidos (ver app/api/v1/router.py). Para exercitá-la sem expor tokens nos
testes, o fixture `client` sobrescreve `get_current_user` com um usuário já
persistido no banco de teste. O fixture `anon_client` NÃO sobrescreve a guarda,
deixando-a intacta para os testes de autenticação (401 sem token válido).
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.deps import get_current_user
from app.core.database import get_session
from app.main import create_app
from app.models import Base  # importa e registra todos os modelos no metadata
from app.models.user import User


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_auth_user(session_factory) -> User:
    """Persiste um usuário fixo para a guarda JWT dos testes autenticados."""
    async with session_factory() as s:
        user = User(
            id=uuid4(),
            email="test-auth@example.com",
            display_name="Test Auth",
            password_hash=None,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        # Desanexa para evitar lazy-load com sessão fechada no override.
        await s.refresh(user, attribute_names=["id", "email", "display_name"])
        return User(id=user.id, email=user.email, display_name=user.display_name)


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()

    auth_user = await _seed_auth_user(session_factory)

    async def override_session() -> AsyncSession:
        async with session_factory() as s:
            yield s

    async def override_current_user() -> User:
        return auth_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client(session_factory):
    """Cliente SEM bypass de auth — exercita a guarda real (get_current_user).

    Usado pelos testes de autenticação. Não injeta usuário: endpoints
    protegidos devem retornar 401 sem token válido.
    """
    app = create_app()

    async def override() -> AsyncSession:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()
