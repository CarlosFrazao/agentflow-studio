"""Testes de integração do CodeResearchAgent no pipeline (item 4).

Verifica que, ao rodar a etapa 'research', o CodeResearchAgent é executado e
seu output é persistido como Artifact (agent_name='code_research'); e que a
etapa 'planner' subsequente consome esse conteúdo (aparece no raw_plan do
PlannerAgent, que concatena CODE_RESEARCH no prompt).

Agents são monkeypatchados para não depender de LLM/rede externa.
"""

import json
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Artifact
from app.services.agents.code_research import CodeResearchAgent, CodeResearchOutput
from app.services.agents.research import ResearchAgent, ResearchOutput
from app.services.agents.planner import PlannerAgent, PlannerOutput

pytestmark = pytest.mark.asyncio


async def _seed_card_in_column(client, column: str) -> str:
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards",
        json={"project_id": pid, "title": "Ideia", "column": column},
    )
    return card.json()["data"]["id"]


async def test_code_research_artifact_created_and_consumed_by_planner(
    client, session_factory, monkeypatch
) -> None:
    # Stubs sem rede/LLM
    async def fake_research(self, query, mode="guerrilha"):
        return ResearchOutput(sra_report="# relatorio", confidence=0.9)

    async def fake_code_research(self, *args, **kwargs):
        return CodeResearchOutput(
            suggestions=["use pydantic"], license_class="permissive"
        )

    async def fake_planner(self, ideation, research, code_research):
        return PlannerOutput(raw_plan=f"CODE_RESEARCH:{code_research}")

    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(CodeResearchAgent, "run", fake_code_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)

    cid = await _seed_card_in_column(client, "researching")
    cid_uuid = UUID(cid)

    # Etapa research -> dispara Research + CodeResearch
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200, resp.text

    # Artifact de code_research persistido
    async with session_factory() as s:
        stored = await s.execute(
            select(Artifact).where(
                Artifact.card_id == cid_uuid, Artifact.agent_name == "code_research"
            )
        )
        cr_artifact = stored.scalar_one_or_none()
    assert cr_artifact is not None, "Artifact de code_research não foi persistido"
    cr_content = json.loads(cr_artifact.content)
    assert cr_content["suggestions"] == ["use pydantic"]

    # Etapa planner -> consome o artifact (card avançou para 'planning')
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200, resp.text

    async with session_factory() as s:
        planner_art = await s.execute(
            select(Artifact).where(
                Artifact.card_id == cid_uuid, Artifact.agent_name == "planner"
            )
        )
        planner_artifact = planner_art.scalar_one_or_none()
    assert planner_artifact is not None
    # O Planner recebeu o conteúdo de code_research (está no raw_plan,
    # serializado como string JSON dentro do campo).
    assert cr_content["suggestions"][0] in planner_artifact.content
    assert "code_research" in planner_artifact.content.lower() or "CODE_RESEARCH" in planner_artifact.content
