"""Verificação do FLUXO REAL do CodeResearchAgent via endpoint /run.

Diferente de test_code_research_artifact.py (que monkeypatcha as classes de
agente), este teste NÃO altera os agents: ele exercita o caminho real de
run.py (_dispatch -> CodeResearchAgent -> persist artifact -> Planner consome).
Para isso, injetamos fakes SÓ nos clients externos (llm/sra/firecrawl/github)
via app.state.service_overrides — exatamente como a app faria em produção,
mas sem precisar de rede/LLM reais. demo_mode fica False (fluxo real).

Prova que:
1) o artifact 'code_research' é persistido no banco ao rodar /run na coluna researching;
2) o Planner realmente recebe e usa esse conteúdo no raw_plan (etapa planning).
"""

import json
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.deps import get_current_user, get_session
from app.core.config import Settings
from app.main import create_app
from app.models import Artifact
from app.models.user import User as UserModel
from app.services.llm import LLMClient  # noqa: F401 (usado pelos fakes)

pytestmark = pytest.mark.asyncio


# ---- Fakes dos clients externos (sem rede) ----
class FakeLLM(LLMClient):
    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        # Devolve algo determinístico para o Code Research e para o Planner.
        if "Code Research Agent" in system_prompt:
            return {"suggestions": ["use_fastapi"], "license_class": "permissive"}
        return {"title": "Plano X", "stack": ["fastapi"], "milestones": [], "risks": []}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return "texto"


class FakeSRA:
    async def research(self, query: str, mode: str = "guerrilha") -> str:
        return "# Relatorio de mercado"


class FakeFirecrawl:
    async def scrape(self, url: str) -> dict:
        return {"data": {"markdown": "# docs externos do repo"}}


class FakeGitHub:
    async def search_repos(self, query: str, per_page: int = 15) -> list[dict]:
        return [{"full_name": "owner/repo", "description": "d"}]

    async def get_file(self, repo: str, path: str, ref: str = "main") -> str:
        if path == "LICENSE":
            return "MIT License"
        return "# README"


async def test_real_flow_persists_code_research_and_planner_consumes_it(
    session_factory, monkeypatch
) -> None:
    # demo_mode desligado para garantir fluxo real (sem contorno de agents).
    monkeypatch.setattr(
        "app.api.v1.run.get_settings",
        lambda: Settings(demo_mode=False),
    )

    app = create_app()
    async with session_factory() as s:
        user = UserModel(
            id=UUID(int=4),  # uuid fixo p/ teste
            email="real-flow@example.com",
            display_name="RF",
            password_hash=None,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)

    # Injeção de fakes nos clients externos (como a app faria em produção).
    app.state.service_overrides = {
        "llm": FakeLLM(),
        "sra": FakeSRA(),
        "firecrawl": FakeFirecrawl(),
        "github": FakeGitHub(),
    }

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Cria projeto + card na coluna researching (dispara research no /run)
        proj = await client.post("/api/v1/projects", json={"name": "P"})
        pid = proj.json()["data"]["id"]
        card = await client.post(
            "/api/v1/cards",
            json={"project_id": pid, "title": "App de Tarefas", "column": "researching"},
        )
        cid = UUID(card.json()["data"]["id"])

        # 1) roda etapa research -> CodeResearchAgent é chamado de verdade
        resp = await client.post(f"/api/v1/cards/{cid}/run")
        assert resp.status_code == 200, resp.text

        # Confirma artifact code_research no banco
        async with session_factory() as s:
            cr = await s.execute(
                select(Artifact).where(
                    Artifact.card_id == cid, Artifact.agent_name == "code_research"
                )
            )
            cr_artifact = cr.scalar_one_or_none()
        assert cr_artifact is not None, "code_research NÃO foi persistido no fluxo real"
        cr_content = json.loads(cr_artifact.content)
        assert cr_content["suggestions"] == ["use_fastapi"]

        # 2) roda etapa planning -> Planner consome o artifact
        resp = await client.post(f"/api/v1/cards/{cid}/run")
        assert resp.status_code == 200, resp.text

        async with session_factory() as s:
            pl = await s.execute(
                select(Artifact).where(
                    Artifact.card_id == cid, Artifact.agent_name == "planner"
                )
            )
            planner_artifact = pl.scalar_one_or_none()
        assert planner_artifact is not None
        # O Planner recebeu o conteúdo de code_research (está no raw_plan)
        assert "use_fastapi" in planner_artifact.content
        assert "CODE_RESEARCH" in planner_artifact.content
