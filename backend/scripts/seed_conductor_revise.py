"""Seed determinístico para validação FEAT-008 (revise_artifact) do Conductor.

Cria um projeto + card em 'planning' (coluna onde o Planner já rodou) com os
artifacts a montante (ideation/research/code_research/planner) presentes, e uma
conversa vinculada ao card. O script ARES então envia "troca a stack pra
Postgres" pelo chat e valida que o card NÃO sai de 'planning' (revise_artifact
cria nova versão sem re-rodar o montante e sem avançar coluna).

Uso:
    python backend/scripts/seed_conductor_revise.py
Imprime: <card_id> <conversation_id>  (consumido pelo script ARES FEAT-008)
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

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
from app.models.artifact import Artifact  # noqa: E402
from app.models.conversation import Conversation  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.card import Card  # noqa: E402

DEFAULT_PROJECT_NAME = "PRD v1.1 — Pipeline Multi-Agente"
PLANNER_CONTENT = (
    '{"title": "App de Caronas", "stack": ["python", "fastapi"], '
    '"milestones": ["M1", "M2"], "risks": ["seguranca"]}'
)
IDEO_CONTENT = (
    '{"project_name": "CaronasFaculdade", "key_features": ["match", "rotas"], '
    '"elevator_pitch": "p", "confidence_score": 0.9}'
)
RESEARCH_CONTENT = "# Relatorio de Pesquisa\n\n## Concorrentes\n- BlaBlaCar"
CR_CONTENT = '{"suggestions": ["exemplo"], "license_class": "permissive"}'


async def main() -> str:
    async with AsyncSessionFactory() as s:
        result = await s.execute(
            select(Project).where(Project.name == DEFAULT_PROJECT_NAME)
        )
        proj = result.scalars().first()
        if proj is None:
            proj = Project(name=DEFAULT_PROJECT_NAME)
            s.add(proj)
            await s.commit()
            await s.refresh(proj)

        card = Card(
            project_id=proj.id,
            column="planning",
            title="App de Caronas para Faculdade",
        )
        s.add(card)
        await s.commit()
        await s.refresh(card)

        # Artifacts a montante + planner (necessários para re-executar o planner).
        for agent, content in (
            ("ideation", IDEO_CONTENT),
            ("research", RESEARCH_CONTENT),
            ("code_research", CR_CONTENT),
            ("planner", PLANNER_CONTENT),
        ):
            s.add(
                Artifact(
                    card_id=card.id, agent_name=agent, type="json", content=content
                )
            )
        await s.commit()

        # Conversa vinculada ao card.
        conv = Conversation(project_id=proj.id, card_id=card.id)
        s.add(conv)
        await s.commit()
        await s.refresh(conv)

        # Mensagens de contexto para o chat não ficar vazio.
        from app.models.conversation import Message

        s.add(
            Message(
                conversation_id=conv.id,
                role="user",
                content="quero um app de caronas para a faculdade",
            )
        )
        s.add(
            Message(
                conversation_id=conv.id,
                role="conductor",
                content="Plano tecnico pronto (stack: python, fastapi).",
            )
        )
        await s.commit()

        # Saída: card_id conversation_id (capturada pelo script ARES).
        return f"{card.id} {conv.id}"


if __name__ == "__main__":
    import asyncio
    import logging

    # Silencia o log do SQLAlchemy para que a stdout contenha APENAS os ids
    # (card_id conversation_id), facilitando o parse pelo script ARES.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    out = asyncio.run(main())
    print(out)
