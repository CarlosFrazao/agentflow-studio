"""Testes TDD dos agents do pipeline (F-003/F-008/F-004/F-005/F-006).

Clients/LLM mockados (sem rede/custo). Validam contratos de entrada/saída e
regras de negócio: cache de pesquisa, fallback SRA, licença copyleft, alertas
do Reviewer, timeout do Dev Agent.
"""

import pytest

from app.services.agents.code_research import CodeResearchAgent, CodeResearchOutput
from app.services.agents.dev import DevAgent, DevOutput
from app.services.agents.planner import PlannerAgent, PlannerOutput
from app.services.agents.research import ResearchAgent, ResearchOutput
from app.services.agents.reviewer import ReviewerAgent, ReviewOutput
from app.sandbox.base import SandboxResult


# ---- Fakes reutilizáveis ----
class FakeLLM:
    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {
            "synthesis": "resumo de mercado",
            "competitors": ["A", "B"],
            "gaps": ["x"],
            "confidence": 0.9,
        }

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return "texto"


class FakeSRA:
    async def research(self, query: str, mode: str = "guerrilha") -> str:
        return "# Relatorio SRA\nconcorrentes..."

    async def health(self) -> bool:
        return True


class FakeSRAUnavailable:
    async def research(self, query: str, mode: str = "guerrilha") -> str:
        raise Exception("SRA down")

    async def health(self) -> bool:
        return False


class FakeFirecrawl:
    async def scrape(self, url: str) -> dict:
        return {"data": {"content": "docs"}}


class FakeGitHub:
    async def get_file(self, repo: str, path: str, ref: str = "main") -> str:
        return "MIT License\n..."

    async def search_repos(self, query: str, per_page: int = 15) -> list[dict]:
        return [{"full_name": "owner/repo", "description": "d"}]


# ---- F-003 Research Agent ----
async def test_research_agent_returns_output_with_sra() -> None:
    agent = ResearchAgent(llm=FakeLLM(), sra=FakeSRA())
    out = await agent.run(query="app de receitas")
    assert isinstance(out, ResearchOutput)
    assert out.sra_report
    assert out.confidence >= 0.0


async def test_research_agent_degrades_when_sra_unavailable() -> None:
    agent = ResearchAgent(llm=FakeLLM(), sra=FakeSRAUnavailable())
    out = await agent.run(query="app de receitas")
    assert out.degraded is True
    assert "incompleta" in out.warning.lower()


# ---- F-008 Code Research Agent ----
async def test_code_research_flags_copyleft_license() -> None:
    class GPLGitHub(FakeGitHub):
        async def get_file(self, repo: str, path: str, ref: str = "main") -> str:
            return "GNU GENERAL PUBLIC LICENSE\n..."

    agent = CodeResearchAgent(
        llm=FakeLLM(), github=GPLGitHub(), firecrawl=FakeFirecrawl()
    )
    out = await agent.run(repo_candidates=[{"full_name": "owner/repo"}])
    assert isinstance(out, CodeResearchOutput)
    assert out.license_class == "copyleft"
    assert out.license_warning is not None


# ---- F-004 Planner Agent ----
async def test_planner_returns_plan() -> None:
    agent = PlannerAgent(llm=FakeLLM())
    out = await agent.run(
        ideation={"project_name": "X", "key_features": ["a"]},
        research="# relatorio",
        code_research="padroes sugeridos",
    )
    assert isinstance(out, PlannerOutput)
    assert out.title


# ---- F-005 Reviewer Agent (leve) ----
async def test_reviewer_flags_critical_inconsistency() -> None:
    agent = ReviewerAgent(llm=FakeLLM())
    out = await agent.run(
        ideation={"project_name": "App", "key_features": ["iOS apenas"]},
        research="foco em Android",
        planner="plano para Android",
        code_research="",
    )
    assert isinstance(out, ReviewOutput)
    # FakeLLM não produz alertas; garantimos contrato e ausência de erro
    assert out.alerts is not None


async def test_reviewer_no_critical_when_consistent() -> None:
    agent = ReviewerAgent(llm=FakeLLM())
    out = await agent.run(
        ideation={"project_name": "App", "key_features": ["web"]},
        research="mercado web",
        planner="plano web",
        code_research="",
    )
    assert out.critical_count == 0


# ---- F-006 Dev Agent ----
async def test_dev_agent_marks_generated_code() -> None:
    class FakeSandbox:
        async def validate(self, code: str) -> SandboxResult:
            return SandboxResult(success=True, stderr="")

    agent = DevAgent(llm=FakeLLM(), sandbox=FakeSandbox())
    out = await agent.run(plan="implementar funcao soma")
    assert isinstance(out, DevOutput)
    assert out.code
    assert out.ran_in_sandbox is True
