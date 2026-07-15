"""Testes de fiação do pipeline (Problemas 1, 2, 3 do run.py).

Verificam o CONTEÚDO real passado entre agentes no endpoint /cards/{id}/run,
não só que cada .run() foi chamado. Todos os agents são monkeypatchados
(sem LLM/rede); o sandbox do Dev Agent é injetado via override de dependência.
"""

import json
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Artifact
from app.services.agents.dev import DevAgent, DevOutput
from app.services.agents.ideation import IdeationAgent, IdeationOutput
from app.services.agents.planner import PlannerAgent, PlannerOutput
from app.services.agents.research import ResearchAgent, ResearchOutput
from app.services.agents.reviewer import ReviewerAgent, ReviewOutput, ReviewAlert
from app.services.agents.code_research import CodeResearchAgent, CodeResearchOutput
from app.sandbox.base import SandboxBackend, SandboxResult

pytestmark = pytest.mark.asyncio


async def _seed_card_in_column(client, column: str, title: str = "Ideia") -> str:
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": title, "column": column}
    )
    return card.json()["data"]["id"]


class _OkSandbox(SandboxBackend):
    name = "ok"

    async def validate(self, code: str) -> SandboxResult:
        return SandboxResult(success=True, stderr="", backend=self.name)


async def test_planner_receives_real_ideation_not_empty(
    client, session_factory, monkeypatch
) -> None:
    """Problema 1: o Planner recebe o JSON real do Ideation (não {})."""
    captured: dict = {}

    async def fake_ideation(self, raw_idea):  # noqa: ANN001
        return IdeationOutput(
            project_name="MeuApp", key_features=["a"], elevator_pitch="p",
            confidence_score=0.9,
        )

    async def fake_research(self, query, mode="guerrilha"):  # noqa: ANN001
        return ResearchOutput(sra_report="# r", confidence=0.9)

    async def fake_planner(self, ideation, research, code_research):  # noqa: ANN001
        captured["ideation"] = ideation
        captured["research"] = research
        return PlannerOutput(raw_plan=f"IDEA:{ideation}")

    monkeypatch.setattr(IdeationAgent, "run", fake_ideation)
    monkeypatch.setattr(ResearchAgent, "run", fake_research)
    monkeypatch.setattr(PlannerAgent, "run", fake_planner)

    cid = await _seed_card_in_column(client, "planning")
    cid_uuid = UUID(cid)

    # Semeia o artifact de ideation (simula a etapa de ideation já rodada).
    async with session_factory() as s:
        s.add(Artifact(
            card_id=cid_uuid, agent_name="ideation", type="json",
            content=json.dumps({
                "project_name": "MeuApp", "key_features": ["a"],
                "elevator_pitch": "p", "confidence_score": 0.9,
            }),
        ))
        s.add(Artifact(
            card_id=cid_uuid, agent_name="research", type="json",
            content=json.dumps({"sra_report": "relatorio real"}),
        ))
        await s.commit()

    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200, resp.text

    # O Planner recebeu o ideation REAL (não {}).
    assert captured["ideation"] != {}
    assert captured["ideation"]["project_name"] == "MeuApp"
    # E o research REAL (não "") também foi repassado.
    assert "relatorio real" in captured["research"]


async def test_reviewer_receives_all_four_real_artifacts_and_flags_critical(
    client, session_factory, monkeypatch
) -> None:
    """Problema 2 (Definição de Pronto): Reviewer vê os 4 artifacts reais e
    gera um alerta 'critical' quando há contradição real entre ideia e plano."""
    captured: dict = {}

    async def fake_reviewer(self, ideation, research, planner, code_research):  # noqa: ANN001
        captured["ideation"] = ideation
        captured["research"] = research
        captured["planner"] = planner
        captured["code_research"] = code_research
        # Contradição real: ideia diz Python, plano diz Node — alerta crítico.
        return ReviewOutput(
            alerts=[ReviewAlert(message="linguagem diverge", severity="critical")],
            critical_count=1,
            passed=False,
            confidence_score=0.4,
            log_summary="linguagem diverge",
        )

    monkeypatch.setattr(ReviewerAgent, "run", fake_reviewer)

    cid = await _seed_card_in_column(client, "reviewing")
    cid_uuid = UUID(cid)
    async with session_factory() as s:
        for name, content in {
            "ideation": json.dumps({"project_name": "MeuApp", "key_features": ["py"]}),
            "research": "# pesquisa real",
            "planner": json.dumps({"stack": ["nodejs"]}),
            "code_research": json.dumps({"license_class": "permissive"}),
        }.items():
            s.add(Artifact(
                card_id=cid_uuid, agent_name=name, type="json", content=content
            ))
        await s.commit()

    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True

    # Reviewer recebeu os 4 artifacts REAIS (não vazios).
    assert captured["ideation"] != {}
    assert captured["research"] != ""
    assert captured["planner"] != ""
    assert captured["code_research"] != ""

    # O alerta crítico foi capturado pelo orquestrador → reprovado → production.
    card = await client.get(f"/api/v1/cards/{cid}")
    assert card.json()["data"]["column"] == "production"
    meta = card.json()["data"]["meta"]
    assert "review_logs" in meta
    assert "linguagem diverge" in (meta["review_logs"] or "")


async def test_dev_receives_real_planner_plan_and_real_sandbox(
    client, session_factory, monkeypatch
) -> None:
    """Problema 3: o Dev Agent recebe o plano REAL (não a string 'plano') e
    usa o sandbox real injetado (não _NoopSandbox)."""
    captured: dict = {}

    # Dev Agent real, só trocamos o run para capturar o que ele recebeu.
    real_dev_run = DevAgent.run

    async def spy_dev_run(self, plan: str) -> DevOutput:  # noqa: ANN001
        captured["plan"] = plan
        captured["sandbox_class"] = type(self._sandbox).__name__
        return await real_dev_run(self, plan)

    monkeypatch.setattr(DevAgent, "run", spy_dev_run)

    cid = await _seed_card_in_column(client, "production")
    cid_uuid = UUID(cid)
    planner_plan = json.dumps({"title": "MeuApp", "stack": ["py"]})
    async with session_factory() as s:
        s.add(Artifact(
            card_id=cid_uuid, agent_name="planner", type="json", content=planner_plan
        ))
        await s.commit()

    # Injeta um sandbox REAL (não _NoopSandbox) via override de dependência
    # (mesmo mecanismo usado pelos testes de LLM/SRA/Firecrawl). O get_sandbox
    # lê request.app.state["service_overrides"], então setamos direto no app.
    from app.services.deps import _STATE_KEY

    app = client._transport.app  # app criado pelo fixture `client`
    setattr(app.state, _STATE_KEY, {"sandbox": _OkSandbox()})

    resp = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp.status_code == 200, resp.text

    # O Dev recebeu o plano REAL do Planner (não a string fixa "plano").
    assert captured["plan"] == planner_plan
    # O sandbox usado é o real injetado, não o _NoopSandbox.
    assert captured["sandbox_class"] == "_OkSandbox"
