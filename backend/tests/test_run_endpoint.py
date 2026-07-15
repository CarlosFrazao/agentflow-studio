"""Teste TDD do endpoint /cards/{id}/run (orquestrador via API).

Valida: executa agente da coluna atual, persiste Artifact + Execution,
move o card para a próxima coluna, e aplica auto-approve quando aplicável.
LLM/SRA mockados via override de dependência.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _seed_card(client: AsyncClient) -> tuple[str, str]:
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Ideia", "column": "backlog"}
    )
    return pid, card.json()["data"]["id"]


async def test_run_backlog_card_runs_ideation_and_advances(
    client: AsyncClient, monkeypatch
) -> None:
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea: str) -> IdeationOutput:
        return IdeationOutput(
            project_name="X", key_features=["a"], elevator_pitch="p", confidence_score=0.9
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _, cid = await _seed_card(client)
    # sobe o card para a coluna 'backlog' já está; executa
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    # card avançou para researching
    card = await client.get(f"/api/v1/cards/{cid}")
    assert card.json()["data"]["column"] == "researching"
    # artifact criado
    arts = await client.get(f"/api/v1/cards/{cid}/artifacts")
    assert arts.status_code == 200


async def test_run_ideation_high_confidence_auto_approves(
    client: AsyncClient, monkeypatch
) -> None:
    from app.services.agents.ideation import IdeationAgent, IdeationOutput

    async def fake_run(self, raw_idea: str) -> IdeationOutput:
        return IdeationOutput(
            project_name="X",
            key_features=["a"],
            elevator_pitch="p",
            confidence_score=0.95,
        )

    monkeypatch.setattr(IdeationAgent, "run", fake_run)

    _, cid = await _seed_card(client)
    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200
    card = await client.get(f"/api/v1/cards/{cid}")
    data = card.json()["data"]
    assert data["auto_approved"] is True
    assert data["approval_by"] == "auto"
