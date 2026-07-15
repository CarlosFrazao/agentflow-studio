"""Seed idempotente do usuário de teste (v1.2).

Cria (ou mantém) um usuário fixo no SQLite local para uso em E2E/testes
manuais. Reutiliza o modelo `User` e `hash_password` da aplicação, então o
usuário semeado consegue logar de verdade via POST /api/v1/auth/login.

Idempotente: se o e-mail já existir, NÃO recria (preserva o hash/senha atuais).

Uso:
    python scripts/seed_test_user.py
    TEST_USER_EMAIL=qa@exemplo.com TEST_USER_PASSWORD=segura123 \
        python scripts/seed_test_user.py

Variáveis de ambiente (todas opcionais):
    TEST_USER_EMAIL     (default: test@example.com)
    TEST_USER_PASSWORD  (default: test-password-123)
    TEST_USER_NAME      (default: Test User)
    DATABASE_URL        (usa a config da app se ausente)
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

# Garante que `app` seja importável quando o script roda de qualquer diretório.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import _ensure_db_dir
from app.core.security import hash_password
from app.models import Base  # registra todos os modelos no metadata
from app.models.user import User


DEFAULT_EMAIL = "test@example.com"
DEFAULT_PASSWORD = "test-password-123"
DEFAULT_NAME = "Test User"


async def seed() -> None:
    settings = get_settings()
    database_url = os.getenv("DATABASE_URL") or settings.database_url

    email = os.getenv("TEST_USER_EMAIL", DEFAULT_EMAIL)
    password = os.getenv("TEST_USER_PASSWORD", DEFAULT_PASSWORD)
    display_name = os.getenv("TEST_USER_NAME", DEFAULT_NAME)

    # Importa o User para garantir que a tabela esteja no metadata.
    _ = User

    _ensure_db_dir()
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migração defensiva: DBs de fase anterior podem não ter password_hash
        # (create_all não altera tabelas existentes). Adiciona se faltar.
        rows = await conn.exec_driver_sql("PRAGMA table_info(users)")
        cols = {row[1] for row in rows.fetchall()}
        if "password_hash" not in cols:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
            )
            print("[seed] coluna password_hash adicionada ao users (migração)")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            print(f"[seed] usuario ja existe: {email} (id={existing.id})")
            await engine.dispose()
            return

        user = User(
            id=uuid4(),
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"[seed] usuario criado: {email} / senha='{password}' (id={user.id})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
