"""Seed determinístico do histórico longo do Conductor para validação FEAT-007.

Popula o SQLite do AgentFlow com uma conversa + card no projeto padrão
("PRD v1.1 — Pipeline Multi-Agente") contendo 40 mensagens, sendo a PRIMEIRA
a travar o NOME DO PROJETO ("CaronasFaculdade"). As demais são mensagens
longas (cada uma ~500 chars) para estourar o orçamento de tokens do histórico
(CONDUCTOR_HISTORY_TOKEN_BUDGET=3000), forçando o resumo das antigas.

O objetivo é validar, via ARES, que o Conductor PRESERVA o fato da 1ª mensagem
(nome do projeto) mesmo após o resumo do histórico — exatamente o que
`_build_history_within_budget` + `compress_artifact` garantem.

Uso:
    python backend/scripts/seed_conductor_history.py
Imprime o conversation_id criado (consumido pelo script ARES).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Garante que o backend esteja no sys.path.
# - Rodando do repo: backend/scripts/seed_*.py  -> parents[2] == repo, backend em parents[2]/backend
# - Rodando dentro do container: /app/seed_*.py  -> o próprio /app já é o backend
_self = Path(__file__).resolve()
if (_self.parent / "app").is_dir():
    BACKEND_ROOT = _self.parent  # container: /app
elif (_self.parents[1] / "app").is_dir():
    BACKEND_ROOT = _self.parents[1]  # repo: backend/
else:
    BACKEND_ROOT = _self.parents[2] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionFactory  # noqa: E402
from app.models.conversation import Conversation, Message  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.card import Card  # noqa: E402

DEFAULT_PROJECT_NAME = "PRD v1.1 — Pipeline Multi-Agente"
PROJECT_NAME = "CaronasFaculdade"
N_MESSAGES = 40


async def main() -> str:
    async with AsyncSessionFactory() as s:
        # Projeto padrão (mesmo que a UI usa via ensureProject).
        result = await s.execute(
            select(Project).where(Project.name == DEFAULT_PROJECT_NAME)
        )
        proj = result.scalars().first()
        if proj is None:
            proj = Project(name=DEFAULT_PROJECT_NAME)
            s.add(proj)
            await s.commit()
            await s.refresh(proj)

        conv = Conversation(project_id=proj.id)
        s.add(conv)
        await s.commit()
        await s.refresh(conv)

        # Card em 'done' (o Conductor em 'done' usa get_card_state — sem rodar agents).
        card = Card(project_id=proj.id, column="done", title=f"App {PROJECT_NAME}")
        s.add(card)
        await s.commit()
        await s.refresh(card)
        conv.card_id = card.id
        await s.commit()

        base = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(N_MESSAGES):
            if i == 0:
                # 1ª mensagem: TRAVA o nome do projeto (fato crítico a preservar).
                content = (
                    f"vamos criar o projeto {PROJECT_NAME} de caronas para faculdade, "
                    f"focado em trajetos diarios casa-faculdade"
                )
            else:
                content = f"mensagem longa de contexto numero {i:02d} " + "z" * 480
            msg = Message(
                conversation_id=conv.id,
                role="user",
                content=content,
                created_at=base + timedelta(seconds=i),
            )
            s.add(msg)
            await s.commit()

        return str(conv.id)


if __name__ == "__main__":
    import asyncio

    cid = asyncio.run(main())
    # Imprime apenas o id para o script ARES capturar via stdout.
    print(cid)
