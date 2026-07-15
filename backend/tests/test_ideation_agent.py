"""Testes TDD do Ideation Agent (F-002): ideia bruta -> JSON estruturado.

Usa LLM mockado (sem custo/rede). Valida contrato de saída esperado pelo
Research Agent (project_name, key_features, elevator_pitch).
"""

import pytest

from app.services.agents.ideation import IdeationAgent, IdeationOutput


def _make_agent() -> IdeationAgent:
    class FakeLLM:
        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            return {
                "project_name": "App de Receitas",
                "key_features": ["busca por ingredientes", "modo offline"],
                "elevator_pitch": "Ajuda a cozinhar com o que tem em casa.",
                "confidence_score": 0.9,
            }

    return IdeationAgent(llm=FakeLLM())  # type: ignore[arg-type]


async def test_ideation_returns_structured_output() -> None:
    agent = _make_agent()
    result = await agent.run("um app de receitas com o que tem em casa")
    assert isinstance(result, IdeationOutput)
    assert result.project_name == "App de Receitas"
    assert "busca por ingredientes" in result.key_features
    assert result.confidence_score >= 0.85


async def test_ideation_output_is_serializable() -> None:
    agent = _make_agent()
    result = await agent.run("ideia qualquer")
    dumped = result.model_dump()
    assert "project_name" in dumped
    assert "key_features" in dumped
