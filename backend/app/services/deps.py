"""Dependencies de serviço — fornecem LLM e clients externos (com override p/ testes)."""

from typing import Optional

from fastapi import Request

from app.clients.github_client import GitHubClient
from app.clients.mcp.firecrawl_client import FirecrawlClient
from app.clients.mcp.sra_client import SRAClient
from app.core.config import get_settings
from app.services.llm import GeminiClient, LLMClient

# Contexto de request: permite injectar fakes nos testes via app.state
_STATE_KEY = "service_overrides"


def _overrides(request: Request) -> dict:
    if not hasattr(request.app.state, _STATE_KEY):
        setattr(request.app.state, _STATE_KEY, {})
    return getattr(request.app.state, _STATE_KEY)


def get_llm(request: Request) -> LLMClient:
    ov = _overrides(request)
    if "llm" in ov:
        return ov["llm"]
    settings = get_settings()
    return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)


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


def set_service_overrides(request: Request, **kwargs) -> None:
    """Usado nos testes para injetar fakes (llm, sra, firecrawl, github)."""
    _overrides(request).update(kwargs)
