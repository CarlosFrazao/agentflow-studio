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


def _make_agent_with(payload: dict) -> IdeationAgent:
    class FakeLLM:
        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            return payload

    return IdeationAgent(llm=FakeLLM())  # type: ignore[arg-type]


async def test_ideation_populates_full_schema() -> None:
    agent = _make_agent_with(
        {
            "project_name": "App de Receitas",
            "key_features": ["busca por ingredientes"],
            "elevator_pitch": "Ajuda a cozinhar.",
            "confidence_score": 0.9,
            "problem_statement": "Falta ideia do que cozinhar em casa.",
            "target_user": "Pessoas ocupadas que cozinham em casa.",
            "out_of_scope": "Entrega de comida.",
            "open_questions": [],
        }
    )
    result = await agent.run("um app de receitas")
    assert result.problem_statement == "Falta ideia do que cozinhar em casa."
    assert result.target_user == "Pessoas ocupadas que cozinham em casa."
    assert result.out_of_scope == "Entrega de comida."
    assert result.open_questions == []
    # Todos os campos serializáveis via JSON.
    dumped = result.model_dump_json()
    assert "problem_statement" in dumped
    assert "target_user" in dumped
    assert "out_of_scope" in dumped
    assert "open_questions" in dumped


async def test_ideation_signals_ambiguity() -> None:
    agent = _make_agent_with(
        {
            "project_name": "Ideia Vaga",
            "key_features": [],
            "elevator_pitch": "",
            "confidence_score": 0.3,
            "problem_statement": "",
            "target_user": "",
            "out_of_scope": "",
            "open_questions": ["Qual é o público-alvo?", "Qual plataforma?"],
        }
    )
    result = await agent.run("quero um app")
    assert result.open_questions
    assert result.needs_clarification is True


async def test_ideation_clear_when_no_open_questions() -> None:
    agent = _make_agent_with(
        {
            "project_name": "Ideia Clara",
            "key_features": ["a"],
            "elevator_pitch": "p",
            "confidence_score": 0.9,
            "problem_statement": "problema",
            "target_user": "usuario",
            "out_of_scope": "nada",
            "open_questions": [],
        }
    )
    result = await agent.run("ideia bem definida")
    assert result.needs_clarification is False
