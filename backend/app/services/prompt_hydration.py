"""Serviço de Prompt Hydration (Item C do analise_omnigent.md).

Intercepta o input informal do usuário e o enriquece antes de enviar ao
agente executor:
1. Traduz PT -> EN técnico refinado (glossário determinístico, sem I/O).
2. Anexa as regras de governance do CLAUDE.md e o contexto do projeto.

A tradução é feita por um glossário local (sem chamada de rede) para manter
o middleware rápido e determinístico. Pode ser trocado por um LLM leve no
futuro sem mudar a assinatura pública.
"""

from typing import Mapping

# Glossário PT -> EN técnico (termos comuns de produto/engenharia).
_GLOSSARY: dict[str, str] = {
    "faz": "build",
    "cria": "create",
    "crie": "create",
    "fazer": "implement",
    "construir": "build",
    "um": "a",
    "uma": "a",
    "site": "website",
    "página": "page",
    "vendas": "e-commerce",
    "loja": "store",
    "carrinho": "cart",
    "pagamento": "payment",
    "pagamentos": "payments",
    "api": "API",
    "de": "for",
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

_GOVERNANCE_RULES = (
    "GOVERNANCE RULES (from CLAUDE.md):\n"
    "- Follow the AgentFlow Studio MVP pipeline (Idea -> Research -> Plan -> Review -> Code -> Deploy).\n"
    "- Keep changes minimal and surgical; prefer existing patterns.\n"
    "- Human-in-the-loop gate: cards await visual approval before production.\n"
    "- Sandbox all generated code before delivery; never ship unvalidated snippets.\n"
)


def translate_to_technical_en(text: str) -> str:
    """Converte comando informal em PT para EN técnico refinado.

    Tokeniza por espaço, substitui termos conhecidos do glossário e capitaliza
    a primeira letra. Texto já em EN é preservado.
    """
    if not text or not text.strip():
        return text

    tokens = text.split()
    translated = []
    for tok in tokens:
        lowered = tok.lower()
        translated.append(_GLOSSARY.get(lowered, tok))
    result = " ".join(translated).strip()
    # Capitaliza o início de uma frase imperativa.
    if result:
        result = result[0].upper() + result[1:]
    return result


def hydrate_prompt(raw_prompt: str, project_context: Mapping[str, object] | None = None) -> str:
    """Enriquece o prompt do usuário com tradução + regras + contexto.

    Ordem do artefato final (estruturado, nunca texto livre solto):
      [TRANSLATED INSTRUCTION]
      [PROJECT CONTEXT]
      [GOVERNANCE RULES]
    """
    instruction = translate_to_technical_en(raw_prompt)
    parts = [f"INSTRUCTION:\n{instruction}"]

    ctx = project_context or {}
    if ctx:
        ctx_lines = "\n".join(f"- {k}: {v}" for k, v in ctx.items())
        parts.append(f"PROJECT CONTEXT:\n{ctx_lines}")

    parts.append(_GOVERNANCE_RULES)
    return "\n\n".join(parts)
