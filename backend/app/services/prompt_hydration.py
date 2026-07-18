"""Serviço de Prompt Hydration (Item C do analise_omnigent.md).

Intercepta o input informal do usuário e o enriquece antes de enviar ao
agente executor:
1. Traduz PT -> EN técnico refinado.
2. Anexa as regras de governance do CLAUDE.md e o contexto do projeto.

FEAT-002 — Tradução Híbrida (Determinístico + LLM opt-in):
- Sem LLM (default): `DeterministicTranslator` — glossário local, zero I/O,
  síncrono e determinístico (mantém o middleware rápido).
- Com LLM injetado: `LLMTranslator` — tradução fluida via modelo, com
  fallback silencioso para o determinístico em qualquer falha/timeout.

A assinatura pública `translate_to_technical_en(text, llm=None)` permanece
retrocompatível: o caminho síncrono default (llm=None) não muda.
"""

import asyncio
import re
from typing import Mapping, Protocol

from app.services.llm import LLMClient

# Frases multi-palavra (traduzidas ANTES da tokenização palavra-a-palavra, pois
# capturam intenção que se perderia token a token).
_PHRASES: list[tuple[str, str]] = [
    ("carrinho de compras", "shopping cart"),
    ("aceite pagamento", "accept payment"),
    ("aceitar pagamento", "accept payment"),
    ("fazer login", "authenticate"),
    ("banco de dados", "database"),
]

# Glossário PT -> EN técnico (termos comuns de produto/engenharia).
_GLOSSARY: dict[str, str] = {
    "faz": "build",
    "faço": "build",
    "fazendo": "building",
    "cria": "create",
    "crie": "create",
    "criar": "create",
    "criado": "created",
    "criando": "creating",
    "fazer": "implement",
    "construir": "build",
    "um": "a",
    "uma": "a",
    "site": "website",
    "página": "page",
    "vendas": "e-commerce",
    "loja": "store",
    "carrinho": "cart",
    "cartão": "card",
    "cartao": "card",
    "pagamento": "payment",
    "pagamentos": "payments",
    "mostre": "display",
    "mostrar": "display",
    "produtos": "products",
    "produto": "product",
    "quero": "want",
    "usando": "using",
    "api": "API",
    "de": "for",
    "por": "by",
    "e": "and",
    "que": "that",
    "para": "for",
    "com": "with",
    "sem": "without",
    "login": "authentication",
    "usuário": "user",
    "usuários": "users",
    "cadastro": "signup",
    "dashboard": "dashboard",
    "relatório": "report",
    "busca": "search",
    "chat": "chat",
    "bot": "bot",
    "agente": "agent",
    "agentes": "agents",
    "teste": "test",
    "testes": "tests",
    "deploy": "deployment",
    "banco": "database",
    "dados": "data",
}

# Palavras PT frequentes usadas só para detectar resíduo pós-tradução (log).
_PT_RESIDUAL_MARKERS = {"ção", "ções", "ã", "õ"}

_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]+", re.UNICODE)

_GOVERNANCE_RULES = (
    "GOVERNANCE RULES (from CLAUDE.md):\n"
    "- Follow the AgentFlow Studio MVP pipeline (Idea -> Research -> Plan -> Review -> Code -> Deploy).\n"
    "- Keep changes minimal and surgical; prefer existing patterns.\n"
    "- Human-in-the-loop gate: cards await visual approval before production.\n"
    "- Sandbox all generated code before delivery; never ship unvalidated snippets.\n"
)


class TechnicalTranslator(Protocol):
    """Contrato de tradução PT -> EN técnico (injável)."""

    def translate(self, text: str) -> str: ...


def _capitalize_first(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


class DeterministicTranslator:
    """Tradutor local por glossário — zero I/O, síncrono, determinístico.

    Preserva pontuação e siglas (tokens totalmente maiúsculos, ex.: API, JWT,
    URL). Aplica frases multi-palavra antes da substituição token a token.
    """

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text

        working = text
        # 1) Frases multi-palavra (case-insensitive, com fronteira de palavra).
        for pt, en in _PHRASES:
            working = re.sub(rf"\b{re.escape(pt)}\b", en, working, flags=re.IGNORECASE)

        # 2) Substituição token a token preservando pontuação e siglas.
        def _sub(match: re.Match[str]) -> str:
            tok = match.group(0)
            if tok.isupper() and len(tok) >= 2:
                return tok  # sigla preservada (API, JWT, URL...)
            return _GLOSSARY.get(tok.lower(), tok)

        result = _TOKEN_RE.sub(_sub, working).strip()
        return _capitalize_first(result)


class LLMTranslator:
    """Tradutor via LLM (tradução fluida) com fallback determinístico.

    O contrato público é síncrono; como `LLMClient.generate_text` é async, a
    chamada roda via `asyncio.run` (mesmo padrão da compressão de artefatos).
    Qualquer falha (rede, timeout, loop ativo) cai no DeterministicTranslator.
    """

    _SYSTEM = (
        "You are a technical translator. Translate the user's product/engineering "
        "request from Portuguese to concise technical English. Preserve acronyms "
        "(API, JWT, URL). Reply ONLY with the translated sentence, no preamble."
    )

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text
        try:
            translated = asyncio.run(
                self._llm.generate_text(system_prompt=self._SYSTEM, user_prompt=text)
            )
            cleaned = (translated or "").strip()
            if cleaned:
                return _capitalize_first(cleaned)
        except Exception:  # noqa: BLE001 — fail-open para o determinístico.
            pass
        return DeterministicTranslator().translate(text)


def translate_to_technical_en(text: str, llm: LLMClient | None = None) -> str:
    """Converte comando informal em PT para EN técnico refinado.

    - `llm is None` (default): usa `DeterministicTranslator` (zero I/O, síncrono).
    - `llm` fornecido: usa `LLMTranslator` (fluido, com fallback determinístico).

    Assinatura pública INALTERADA em relação ao caminho síncrono anterior.
    """
    translator: TechnicalTranslator = (
        LLMTranslator(llm) if llm is not None else DeterministicTranslator()
    )
    return translator.translate(text)


def hydrate_prompt(
    raw_prompt: str,
    project_context: Mapping[str, object] | None = None,
    llm: LLMClient | None = None,
) -> str:
    """Enriquece o prompt do usuário com tradução + regras + contexto.

    Ordem do artefato final (estruturado, nunca texto livre solto):
      [TRANSLATED INSTRUCTION]
      [PROJECT CONTEXT]
      [GOVERNANCE RULES]

    `llm=None` (default) mantém o caminho síncrono determinístico intacto.
    """
    instruction = translate_to_technical_en(raw_prompt, llm=llm)
    parts = [f"INSTRUCTION:\n{instruction}"]

    ctx = project_context or {}
    if ctx:
        ctx_lines = "\n".join(f"- {k}: {v}" for k, v in ctx.items())
        parts.append(f"PROJECT CONTEXT:\n{ctx_lines}")

    parts.append(_GOVERNANCE_RULES)
    return "\n\n".join(parts)
