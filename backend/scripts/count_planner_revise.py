"""Conta artifacts de planner de um card (validação FEAT-008 E2E).

Uso (dentro do container):
    python count_planner_revise.py <card_id>
Imprime o número de artifacts de planner do card.
"""

from __future__ import annotations

import sys
from pathlib import Path

_self = Path(__file__).resolve()
if (_self.parent / "app").is_dir():
    BACKEND_ROOT = _self.parent
elif (_self.parents[1] / "app").is_dir():
    BACKEND_ROOT = _self.parents[1]
else:
    BACKEND_ROOT = _self.parents[2] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select, func  # noqa: E402
from uuid import UUID  # noqa: E402

from app.core.database import AsyncSessionFactory  # noqa: E402
from app.models.artifact import Artifact  # noqa: E402

CARD_ID = UUID(sys.argv[1])


async def main() -> int:
    async with AsyncSessionFactory() as s:
        count = (
            await s.execute(
                select(func.count())
                .select_from(Artifact)
                .where(Artifact.card_id == CARD_ID, Artifact.agent_name == "planner")
            )
        ).scalar_one()
        return int(count)


if __name__ == "__main__":
    import asyncio
    import logging

    # Silencia TODOS os loggers do SQLAlchemy (inclusive sqlalchemy.engine)
    # para que a stdout contenha APENAS o número da contagem.
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
    print(asyncio.run(main()))
