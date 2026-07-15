"""Testes TDD de Prompt Hydration (Item C do analise_omnigent.md).

O middleware intercepta o input do usuário e:
1. Traduz comandos em PT para EN técnico refinado.
2. Anexa as regras de código do CLAUDE.md e contexto do projeto.
3. Garante que o agente executor gaste menos tokens em retrabalho.
"""

import pytest

from app.services.prompt_hydration import hydrate_prompt, translate_to_technical_en


def test_translate_portuguese_to_technical_english() -> None:
    """Comando informal em PT vira EN técnico, preservando a intenção."""
    raw = "faz um site de vendas com carrinho"
    result = translate_to_technical_en(raw)
    assert "build" in result.lower() or "create" in result.lower()
    assert "e-commerce" in result.lower() or "cart" in result.lower()
    # Nunca deve permanecer em português
    assert "faz" not in result.lower()


def test_hydrate_appends_claude_md_rules() -> None:
    """O prompt hidratado inclui as regras de governance do CLAUDE.md."""
    raw = "cria uma API de pagamentos"
    result = hydrate_prompt(raw, project_context={"name": "Checkout"})
    assert "CLAUDE.md" in result or "governance" in result.lower() or "rule" in result.lower()
    assert "Checkout" in result  # contexto do projeto anexado


def test_hydrate_is_idempotent_for_already_english() -> None:
    """Se o input já estiver em EN técnico, continua legível e enriquecido."""
    raw = "Implement a REST API for payments using FastAPI"
    result = hydrate_prompt(raw, project_context={})
    assert "FastAPI" in result
    assert "payments" in result


# ---------------------------------------------------------------------------
# FEAT-002: Tradução Técnica Híbrida (Determinístico + LLM opt-in)
# ---------------------------------------------------------------------------


def test_translate_complex_sentence_to_english() -> None:
    """Frase multi-cláusula PT vira EN sem resíduo em português."""
    raw = "quero um site que mostre produtos e aceite pagamento por cartão"
    result = translate_to_technical_en(raw)
    low = result.lower()
    assert "aceite" not in low
    assert "cartão" not in low
    assert "payment" in low
    assert "cart" in low or "card" in low


def test_translate_respects_injected_llm() -> None:
    """Com LLM injetado, o LLMTranslator é usado e produz EN fluida."""

    class StubLLM:
        def __init__(self) -> None:
            self.called = False

        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            self.called = True
            return "Build an e-commerce website with a shopping cart"

        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            return {}

    stub = StubLLM()
    result = translate_to_technical_en(
        "faz um site de vendas com carrinho", llm=stub
    )
    assert stub.called is True
    assert "shopping cart" in result.lower()


def test_translate_deterministic_with_no_llm() -> None:
    """Sem LLM, usa o DeterministicTranslator (zero I/O) e preserva siglas."""
    raw = "cria uma API usando JWT"
    result = translate_to_technical_en(raw, llm=None)
    assert "API" in result  # sigla preservada
    assert "JWT" in result  # sigla preservada
    assert "create" in result.lower()
    assert "cria" not in result.lower()


def test_translate_fallback_on_llm_error() -> None:
    """Se o LLM lança exceção, cai no DeterministicTranslator sem propagar."""

    class BrokenLLM:
        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("boom")

        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            return {}

    result = translate_to_technical_en("faz um site de vendas", llm=BrokenLLM())
    low = result.lower()
    assert "build" in low or "create" in low
    assert "faz" not in low
