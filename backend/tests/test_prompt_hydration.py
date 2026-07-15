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
