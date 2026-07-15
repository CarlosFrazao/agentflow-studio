"""Testes da Fase B1 — Compressão de Artefatos entre Agentes.

Cobre `prune_tool_output` (pré-passe barato, sem LLM) e `compress_artifact`
(resumo via modelo auxiliar mockado). Nenhum teste faz rede: o `call_aux_llm`
é sempre substituído por um mock (monkeypatch).

A substring proibida (nome do ecossistema de origem) é montada por
concatenação para exercitar a varredura sem violar a Regra Suprema.
"""

import asyncio

import pytest

from app.services import artifact_compressor as ac
from app.services.artifact_compressor import (
    COMPRESS_THRESHOLD_CHARS,
    compress_artifact,
    prune_tool_output,
)

# Marca só os testes async (os síncronos de prune não devem carregar a marca).
asyncio_test = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixture: relatório SRA de exemplo (>= 8k chars, 8 seções)
# ---------------------------------------------------------------------------

def _build_big_sra_report() -> str:
    filler = "Detalhe de contexto irrelevante para o resumo. " * 40
    sections = [
        "# Relatório de Pesquisa (SRA)",
        "## Síntese\n" + filler,
        "## Concorrentes\n- Acme Corp (líder de mercado)\n- Beta Tools\n" + filler,
        "## Discussões\n" + filler,
        "## Gaps de Mercado\n- Falta integração nativa com CI\n- Sem tier free real\n" + filler,
        "## Fontes\n- github.com/exemplo\n- news.ycombinator.com/item\n" + filler,
        "## Tendências\n" + filler,
        "## Riscos\n" + filler,
        "## Recomendações\n" + filler,
    ]
    return "\n\n".join(sections)


@pytest.fixture
def big_report() -> str:
    report = _build_big_sra_report()
    assert len(report) >= 8000, f"fixture precisa ser >= 8k chars, tem {len(report)}"
    return report


# ---------------------------------------------------------------------------
# prune_tool_output (sem LLM)
# ---------------------------------------------------------------------------

def test_prune_short_text_is_unchanged() -> None:
    short = "linha curta de saída"
    assert prune_tool_output(short) == short


def test_prune_preserves_head_and_tail() -> None:
    text = "\n".join(f"linha {i}" for i in range(500))
    pruned = prune_tool_output(text)
    assert len(pruned) < len(text)
    assert "linha 0" in pruned  # head preservado
    assert "linha 499" in pruned  # tail preservado
    assert "truncad" in pruned.lower()  # marcador de corte inserido


def test_prune_empty_string() -> None:
    assert prune_tool_output("") == ""


# ---------------------------------------------------------------------------
# compress_artifact (LLM auxiliar mockado)
# ---------------------------------------------------------------------------

@asyncio_test
async def test_below_threshold_returns_original(monkeypatch) -> None:
    called = False

    async def _fake_aux(system_prompt: str, user_prompt: str) -> str:
        nonlocal called
        called = True
        return "NAO DEVERIA SER CHAMADO"

    monkeypatch.setattr(ac, "call_aux_llm", _fake_aux)
    small = "x" * (COMPRESS_THRESHOLD_CHARS - 1)
    out = await compress_artifact(small)
    assert out == small
    assert called is False  # não gasta LLM abaixo do threshold


@asyncio_test
async def test_large_report_compressed_to_30_percent(monkeypatch, big_report) -> None:
    async def _fake_aux(system_prompt: str, user_prompt: str) -> str:
        return (
            "## Síntese\nResumo curto.\n"
            "## Concorrentes\n- Acme Corp\n- Beta Tools\n"
            "## Gaps de Mercado\n- Falta CI nativo\n- Sem tier free\n"
            "## Fontes\n- github.com/exemplo"
        )

    monkeypatch.setattr(ac, "call_aux_llm", _fake_aux)
    out = await compress_artifact(big_report)
    # <= 30% do original (critério de aceitação)
    assert len(out) <= 0.30 * len(big_report)
    # preserva concorrentes e gaps
    assert "Concorrentes" in out
    assert "Gaps" in out


@asyncio_test
async def test_compression_preserves_key_terms_in_prompt(monkeypatch, big_report) -> None:
    captured: dict[str, str] = {}

    async def _fake_aux(system_prompt: str, user_prompt: str) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "## Concorrentes\nx\n## Gaps de Mercado\ny"

    monkeypatch.setattr(ac, "call_aux_llm", _fake_aux)
    await compress_artifact(big_report)
    # o prompt de sistema instrui a preservar as seções-chave
    joined = (captured["system"] + captured["user"]).lower()
    assert "concorrent" in joined
    assert "gap" in joined


@asyncio_test
async def test_aux_failure_degrades_to_pruned_original(monkeypatch, big_report) -> None:
    from app.services.llm import LLMError

    async def _fake_aux(system_prompt: str, user_prompt: str) -> str:
        raise LLMError("provedor auxiliar caiu")

    monkeypatch.setattr(ac, "call_aux_llm", _fake_aux)
    out = await compress_artifact(big_report)
    # Fail-safe: nunca levanta; retorna algo <= original (pré-passe de prune).
    assert isinstance(out, str)
    assert len(out) <= len(big_report)
    assert out  # não vazio


@asyncio_test
async def test_empty_input_returns_empty(monkeypatch) -> None:
    async def _fake_aux(system_prompt: str, user_prompt: str) -> str:
        return "x"

    monkeypatch.setattr(ac, "call_aux_llm", _fake_aux)
    assert await compress_artifact("") == ""


def test_module_has_no_forbidden_token() -> None:
    """Regra Suprema: o módulo não pode conter a substring proibida."""
    import inspect

    forbidden = "he" + "rmes"
    source = inspect.getsource(ac)
    assert forbidden not in source.lower()


def test_verification_snippet_works() -> None:
    """Reproduz o snippet de verificação do plano (adaptado para async)."""
    async def _fake_aux(system_prompt: str, user_prompt: str) -> str:
        return "resumo curto"

    ac.call_aux_llm = _fake_aux  # type: ignore[assignment]
    try:
        result = asyncio.run(compress_artifact("x" * 9000))
        assert isinstance(result, str)
        assert len(result) < 9000
    finally:
        # restaura o símbolo original do módulo
        import importlib

        importlib.reload(ac)
