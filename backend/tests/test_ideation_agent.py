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


async def test_ideation_preserves_valid_llm_name() -> None:
    agent = _make_agent_with(
        {
            "project_name": "UniRide",
            "key_features": ["a"],
            "elevator_pitch": "p",
            "confidence_score": 0.85,
            "open_questions": [],
        }
    )
    result = await agent.run("quero criar um app de caronas para a faculdade")
    # A valid LLM-provided name must be kept as-is (no placeholder, no override).
    assert result.project_name == "UniRide"
    assert result.project_name != "Projeto sem nome"


async def test_ideation_derives_name_when_llm_omits_it() -> None:
    agent = _make_agent_with(
        {
            # Weak free-tier model omitted the name (or returned empty/whitespace).
            "project_name": "",
            "key_features": [],
            "elevator_pitch": "",
            "confidence_score": 0.0,
            "open_questions": [],
        }
    )
    result = await agent.run("quero criar um app de caronas para a faculdade")
    # Must NOT surface the useless placeholder; derive a readable, grammatical name.
    assert result.project_name != "Projeto sem nome"
    assert result.project_name == "App de Caronas para a faculdade"


async def test_ideation_derives_name_when_llm_returns_whitespace() -> None:
    agent = _make_agent_with(
        {
            "project_name": "   ",
            "key_features": [],
            "elevator_pitch": "",
            "confidence_score": 0.0,
            "open_questions": [],
        }
    )
    result = await agent.run("sistema de agendamento de salas")
    assert result.project_name != "Projeto sem nome"
    assert result.project_name == "App de Agendamento de salas"


def test_derive_name_from_bare_noun_prefixes_app() -> None:
    from app.services.agents.ideation import _derive_name

    # Bare noun with no product word -> "App de <Noun>".
    assert _derive_name("caronas") == "App de Caronas"


def test_derive_name_strips_leading_intent_prefix() -> None:
    from app.services.agents.ideation import _derive_name

    # Preserves mid-sentence prepositions (grammar-friendly). A generic product
    # noun in the original idea is re-introduced as "App de" regardless of the
    # exact noun used ("app"/"site"/"sistema").
    assert _derive_name("quero criar um app de caronas para a faculdade") == (
        "App de Caronas para a faculdade"
    )
    assert _derive_name("fazer um site de vendas de cafes artesanais") == (
        "App de Vendas de cafes artesanais"
    )
    # Bare intent verbs without a product noun keep the sentence as-is.
    assert _derive_name("quero criar algo para organizar tarefas") == (
        "Algo para organizar tarefas"
    )


def test_derive_name_preserves_grammar_without_prefix() -> None:
    from app.services.agents.ideation import _derive_name

    # No intent prefix -> sentence-case (first letter up), keep prepositions.
    assert _derive_name("receitas com o que tem em casa") == (
        "Receitas com o que tem em casa"
    )


def test_derive_name_empty_idea_is_neutral() -> None:
    from app.services.agents.ideation import _derive_name

    assert _derive_name("").strip() == "Novo Projeto"
    assert _derive_name("   ").strip() == "Novo Projeto"

