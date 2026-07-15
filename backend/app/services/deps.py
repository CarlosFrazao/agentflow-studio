"""Dependencies de serviço — fornecem LLM e clients externos (com override p/ testes)."""

from typing import Optional

from fastapi import Request

from app.clients.github_client import GitHubClient
from app.clients.mcp.firecrawl_client import FirecrawlClient
from app.clients.mcp.sra_client import SRAClient
from app.sandbox.base import SandboxBackend, get_sandbox_backend
from app.services.llm import (
    GeminiClient,
    LLMClient,
    build_llm_chain,
    call_with_fallback,
)

# Contexto de request: permite injectar fakes nos testes via app.state
_STATE_KEY = "service_overrides"


def _overrides(request: Request) -> dict:
    if not hasattr(request.app.state, _STATE_KEY):
        setattr(request.app.state, _STATE_KEY, {})
    return getattr(request.app.state, _STATE_KEY)


class _FallbackLLMClient(LLMClient):
    """Adapter que roteia generate_json/generate_text pela cadeia de fallback.

    Respeita a ordem de `build_llm_chain` (OpenRouter -> Groq -> Gemini ->
    Ollama), garantindo que uma quota/erro de um provedor (ex.: 429 do Gemini
    free tier) não derrube o pipeline — ele caí para o próximo disponível.
    Substitui o retorno direto de `GeminiClient`, que ignorava a cadeia.
    """

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return await call_with_fallback(
            system_prompt, user_prompt, json_mode=True
        )

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return await call_with_fallback(
            system_prompt, user_prompt, json_mode=False
        )


def get_llm(request: Request) -> LLMClient:
    ov = _overrides(request)
    if "llm" in ov:
        return ov["llm"]
    # Fallback automático entre provedores configurados (LLM_PROVIDER + chaves).
    # Se nenhum provedor estiver configurado, a cadeia vazia levanta LLMError
    # na primeira chamada (comportamento等价 ao de antes, porém explícito).
    return _FallbackLLMClient()


def get_sra(request: Request) -> SRAClient:
    ov = _overrides(request)
    if "sra" in ov:
        return ov["sra"]
    return SRAClient()


def get_firecrawl(request: Request) -> FirecrawlClient:
    ov = _overrides(request)
    if "firecrawl" in ov:
        return ov["firecrawl"]
    return FirecrawlClient()


def get_github(request: Request) -> GitHubClient:
    ov = _overrides(request)
    if "github" in ov:
        return ov["github"]
    return GitHubClient()


def get_sandbox(request: Request) -> SandboxBackend:
    """Backend de sandbox real para o Dev Agent (DockerSandbox por padrão).

    Injetável via app.state["service_overrides"]["sandbox"] nos testes.
    """
    ov = _overrides(request)
    if "sandbox" in ov:
        return ov["sandbox"]
    return get_sandbox_backend()


def set_service_overrides(request: Request, **kwargs) -> None:
    """Usado nos testes para injetar fakes (llm, sra, firecrawl, github)."""
    _overrides(request).update(kwargs)
