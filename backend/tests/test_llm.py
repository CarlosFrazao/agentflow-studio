"""Testes da camada LLM (Item 5 — cobertura de llm.py) sem rede.

Usa:
- `httpx.MockTransport` para interceptar chamadas dos clients HTTP
  (OpenRouter, Groq, Ollama) sem sair da máquina.
- `monkeypatch` do `google.genai` para o GeminiClient.
- `FakeLLMClient` (contrato LLMClient) para validar a cadeia de fallback
  (`build_llm_chain`, `call_with_fallback`, `get_llm_client`).
"""

import json
from typing import Any

import httpx
import pytest

from app.core.config import get_settings
from app.services.llm import (
    LLMClient,
    LLMError,
    OpenRouterClient,
    GroqClient,
    OllamaClient,
    GeminiClient,
    build_llm_chain,
    call_with_fallback,
    get_llm_client,
)

pytestmark = pytest.mark.asyncio


class FakeLLMClient(LLMClient):
    """Implementação falsa do contrato para testar a cadeia de fallback."""

    def __init__(self, name: str = "fake", fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.json_calls = 0
        self.text_calls = 0

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.json_calls += 1
        if self.fail:
            raise RuntimeError(f"{self.name} quebrou")
        return {"ok": True, "name": self.name}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        self.text_calls += 1
        if self.fail:
            raise RuntimeError(f"{self.name} quebrou")
        return f"texto de {self.name}"


def _make_http_client(handler) -> httpx.AsyncClient:
    """Cliente httpx com transporte mockado (sem rede)."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


# ---------------------------------------------------------------------------
# Clients HTTP (OpenRouter / Groq / Ollama) via MockTransport
# ---------------------------------------------------------------------------


async def test_openrouter_generate_json_parses_content() -> None:
    def handler(request):
        body = {
            "choices": [{"message": {"content": json.dumps({"result": "x"})}}]
        }
        return httpx.Response(200, json=body)

    client = OpenRouterClient(api_key="k", model="m", http_client=_make_http_client(handler))
    out = await client.generate_json(system_prompt="s", user_prompt="u")
    assert out == {"result": "x"}


async def test_groq_generate_text_returns_content() -> None:
    def handler(request):
        body = {"choices": [{"message": {"content": "olá"}}]}
        return httpx.Response(200, json=body)

    client = GroqClient(api_key="k", model="m", http_client=_make_http_client(handler))
    out = await client.generate_text(system_prompt="s", user_prompt="u")
    assert out == "olá"


async def test_ollama_generate_json_handles_message_shape() -> None:
    def handler(request):
        body = {"message": {"content": json.dumps({"done": True})}}
        return httpx.Response(200, json=body)

    client = OllamaClient(
        base_url="http://localhost:11434", model="llama3.1", http_client=_make_http_client(handler)
    )
    out = await client.generate_json(system_prompt="s", user_prompt="u")
    assert out == {"done": True}


async def test_openrouter_http_error_raises() -> None:
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    client = OpenRouterClient(api_key="k", model="m", http_client=_make_http_client(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await client.generate_json(system_prompt="s", user_prompt="u")


async def test_openrouter_generate_text_returns_content() -> None:
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "txt"}}]})

    client = OpenRouterClient(api_key="k", model="m", http_client=_make_http_client(handler))
    out = await client.generate_text(system_prompt="s", user_prompt="u")
    assert out == "txt"


async def test_groq_generate_json_parses_content() -> None:
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"g": 1})}}]})

    client = GroqClient(api_key="k", model="m", http_client=_make_http_client(handler))
    out = await client.generate_json(system_prompt="s", user_prompt="u")
    assert out == {"g": 1}


async def test_ollama_generate_text_returns_content() -> None:
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "resp"}})

    client = OllamaClient(
        base_url="http://localhost:11434", model="llama3.1", http_client=_make_http_client(handler)
    )
    out = await client.generate_text(system_prompt="s", user_prompt="u")
    assert out == "resp"


async def test_get_llm_client_returns_first_in_chain(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouter_api_key", "or-key")
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "ollama_base_url", None)
    client = await get_llm_client()
    assert isinstance(client, OpenRouterClient)


# ---------------------------------------------------------------------------
# Gemini via monkeypatch do google.genai
# ---------------------------------------------------------------------------


async def test_gemini_generate_json(monkeypatch) -> None:
    class FakeResponse:
        text = '{"gemini": true}'

    class FakeModels:
        async def generate_content(self, **kwargs):
            return FakeResponse()

    class FakeGenAIClient:
        aio = type("AIO", (), {"models": FakeModels()})()

    class FakeGenAI:
        def __init__(self, api_key=None):
            self._captured = api_key

        def Client(self, api_key):  # type: ignore[attr-defined]
            return FakeGenAIClient()

    # Substitui o módulo google.genai importado por _get_client via
    # `from google import genai` (usa sys.modules).
    import sys

    sys.modules["google"] = type(sys)("google")
    sys.modules["google.genai"] = FakeGenAI()

    client = GeminiClient(api_key="key", model="gemini-2.5-flash")
    out = await client.generate_json(system_prompt="s", user_prompt="u")
    assert out == {"gemini": True}


async def test_gemini_generate_text_error_raises_llmerror(monkeypatch) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs):
            raise ValueError("api fora")

    class FakeGenAIClient:
        aio = type("AIO", (), {"models": FakeModels()})()

    class FakeGenAI:
        def Client(self, api_key):  # type: ignore[attr-defined]
            return FakeGenAIClient()

    import sys

    sys.modules["google.genai"] = FakeGenAI()

    client = GeminiClient(api_key="key", model="gemini-2.5-flash")
    with pytest.raises(LLMError):
        await client.generate_text(system_prompt="s", user_prompt="u")


# ---------------------------------------------------------------------------
# Cadeia de fallback (contrato injetável)
# ---------------------------------------------------------------------------


async def test_build_llm_chain_uses_settings(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouter_api_key", "or-key")
    monkeypatch.setattr(settings, "groq_api_key", "groq-key")
    monkeypatch.setattr(settings, "gemini_api_key", "gem-key")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434")
    chain = build_llm_chain()
    assert len(chain) == 4
    assert isinstance(chain[0], OpenRouterClient)
    assert isinstance(chain[1], GroqClient)
    assert isinstance(chain[2], GeminiClient)
    assert isinstance(chain[3], OllamaClient)


async def test_get_llm_client_raises_when_empty(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "ollama_base_url", None)
    with pytest.raises(LLMError):
        await get_llm_client()


async def test_call_with_fallback_returns_first_success() -> None:
    class AlwaysFails(LLMClient):
        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
            raise RuntimeError("fail 1")

        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("fail 1")

    import app.services.llm as llm_mod
    import unittest.mock as mock

    # 1º falha sempre; 2º (FakeLLMClient) sucede -> fallback retorna o 2º.
    chain = [AlwaysFails(), FakeLLMClient(name="ok")]
    with mock.patch.object(llm_mod, "build_llm_chain", return_value=chain):
        out = await call_with_fallback("s", "u", json_mode=True)
    assert out == {"ok": True, "name": "ok"}


async def test_call_with_fallback_raises_after_all_fail() -> None:
    import app.services.llm as llm_mod
    import unittest.mock as mock

    chain = [FakeLLMClient(name="a", fail=True), FakeLLMClient(name="b", fail=True)]
    with mock.patch.object(llm_mod, "build_llm_chain", return_value=chain):
        with pytest.raises(LLMError):
            await call_with_fallback("s", "u", json_mode=True)


async def test_call_with_fallback_text_mode() -> None:
    import app.services.llm as llm_mod
    import unittest.mock as mock

    with mock.patch.object(llm_mod, "build_llm_chain", return_value=[FakeLLMClient(name="t")]):
        out = await call_with_fallback("s", "u", json_mode=False)
    assert out == "texto de t"


async def test_fallback_llm_client_delegates_to_chain(monkeypatch) -> None:
    """O adapter get_llm() deve rotear pela cadeia de fallback, não fixar Gemini.

    Simula Gemini quebrado (429) e um provedor que sucede na 2a posicao;
    o _FallbackLLMClient deve retornar o resultado do 2o sem levantar.
    """
    import app.services.deps as deps_mod
    import app.services.llm as llm_mod
    import unittest.mock as mock

    class _Broken(LLMClient):
        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
            raise RuntimeError("429 quota")
        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("429 quota")

    class _Ok(LLMClient):
        async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
            return {"narrative": "ok", "tool_calls": []}
        async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
            return "ok"

    with mock.patch.object(llm_mod, "build_llm_chain", return_value=[_Broken(), _Ok()]):
        client = deps_mod._FallbackLLMClient()
        out = await client.generate_json(system_prompt="s", user_prompt="u")
        assert out == {"narrative": "ok", "tool_calls": []}
        txt = await client.generate_text(system_prompt="s", user_prompt="u")
        assert txt == "ok"
