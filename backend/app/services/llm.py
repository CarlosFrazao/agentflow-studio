"""Cliente LLM Multi-provider com Fallback Automático.

Ordem de fallback (configurável via LLM_PROVIDER e chaves disponíveis):
1. OpenRouter (free tier)
2. Groq (free tier)
3. Google Gemini (free tier)
4. Ollama (local, sem chave)

Cada provider implementa o contrato LLMClient (generate_json, generate_text).
Fallback acontece silenciosamente se falhar (rede, auth, rate-limit, etc.).
"""

from abc import ABC, abstractmethod
import json
import os
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("llm")


class LLMError(Exception):
    """Falha de chamada ao provedor de LLM."""


class LLMClient(ABC):
    """Contrato mínimo esperado pelos agents (injável)."""

    @abstractmethod
    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        ...

    async def stream_text(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Yield de chunks de texto (streaming).

        Default: retorna o texto completo de uma vez (fallback para clients sem
        streaming). Subclasses com SSE real sobrescrevem para emitir deltas.
        Usado pelo Conductor para publicar chunks progressivos no WebSocket.
        """
        yield await self.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)


# ---------------------------------------------------------------------------
# Implementações por provedor
# ---------------------------------------------------------------------------

class OpenRouterClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_s
        self._base = "https://openrouter.ai/api/v1/chat/completions"
        self._http_client = http_client

    async def _chat(self, messages: list[dict], response_format: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://agentflow.studio",
            "X-Title": "AgentFlow Studio",
        }
        payload = {"model": self._model, "messages": messages, "temperature": 0.1}
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if self._http_client is not None:
            resp = await self._http_client.post(self._base, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._base, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        data = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json_object",
        )
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        data = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return data["choices"][0]["message"]["content"]


class GroqClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_s
        self._base = "https://api.groq.com/openai/v1/chat/completions"
        self._http_client = http_client

    async def _chat(self, messages: list[dict], response_format: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self._model, "messages": messages, "temperature": 0.1}
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if self._http_client is not None:
            resp = await self._http_client.post(self._base, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._base, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        data = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json_object",
        )
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        data = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return data["choices"][0]["message"]["content"]

    async def stream_text(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Streaming real via SSE (stream=true) da Groq/OpenAI compatível.

        Emite cada delta de conteúdo conforme chega; em falha de parsing ou de
        transporte, recai no generate_text completo (fail-open).
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "stream": True,
        }

        async def _iter_lines(resp):
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:") :].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        try:
            if self._http_client is not None:
                async with self._http_client.stream(
                    "POST", self._base, headers=headers, json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for delta in _iter_lines(resp):
                        yield delta
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    async with client.stream(
                        "POST", self._base, headers=headers, json=payload
                    ) as resp:
                        resp.raise_for_status()
                        async for delta in _iter_lines(resp):
                            yield delta
        except Exception as exc:  # noqa: BLE001
            logger.warning("groq_stream_failed_fallback", error=str(exc))
            yield await self.generate_text(
                system_prompt=system_prompt, user_prompt=user_prompt
            )


class GeminiClient(LLMClient):
    """Wrapper do Google Gemini via o SDK `google.genai` (nova geração)."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout_s: float = 60.0) -> None:
        self._api_key = api_key
        self._model_name = model
        self._timeout = timeout_s
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            client = self._get_client()
            response = await client.aio.models.generate_content(
                model=self._model_name,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config={"response_mime_type": "application/json", "temperature": 0.1},
            )
            return json.loads(response.text)
        except Exception as exc:
            raise LLMError(f"Gemini falhou: {exc}") from exc

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            client = self._get_client()
            response = await client.aio.models.generate_content(
                model=self._model_name,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config={"temperature": 0.1},
            )
            return response.text
        except Exception as exc:
            raise LLMError(f"Gemini falhou: {exc}") from exc

    async def stream_text(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Streaming real do Gemini via generate_content(stream=True)."""
        try:
            client = self._get_client()
            response = await client.aio.models.generate_content(
                model=self._model_name,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config={"temperature": 0.1},
                stream=True,
            )
            async for chunk in response:
                if getattr(chunk, "text", None):
                    yield chunk.text
        except Exception as exc:  # noqa: BLE001
            logger.warning("gemini_stream_failed_fallback", error=str(exc))
            yield await self.generate_text(
                system_prompt=system_prompt, user_prompt=user_prompt
            )


class OllamaClient(LLMClient):
    """Cliente Ollama local (sem chave)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        timeout_s: float = 120.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._http_client = http_client

    async def _chat(self, messages: list[dict], response_format: str | None = None) -> dict:
        payload = {"model": self._model, "messages": messages, "stream": False, "options": {"temperature": 0.1}}
        if response_format == "json_object":
            payload["format"] = "json"
        if self._http_client is not None:
            resp = await self._http_client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        data = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json_object",
        )
        content = data.get("message", {}).get("content", "")
        return json.loads(content)

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        data = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return data.get("message", {}).get("content", "")

    async def stream_text(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Streaming real do Ollama (stream=true retorna NDJSON de deltas)."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {"temperature": 0.1},
        }
        try:
            if self._http_client is not None:
                resp = await self._http_client.post(
                    f"{self._base}/api/chat", json=payload
                )
                resp.raise_for_status()
                for line in resp.text.splitlines():
                    if not line:
                        continue
                    try:
                        piece = json.loads(line)
                        delta = piece.get("message", {}).get("content", "")
                        if delta:
                            yield delta
                    except json.JSONDecodeError:
                        continue
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        f"{self._base}/api/chat", json=payload
                    )
                    resp.raise_for_status()
                    for line in resp.text.splitlines():
                        if not line:
                            continue
                        try:
                            piece = json.loads(line)
                            delta = piece.get("message", {}).get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("ollama_stream_failed_fallback", error=str(exc))
            yield await self.generate_text(
                system_prompt=system_prompt, user_prompt=user_prompt
            )


# ---------------------------------------------------------------------------
# Factory / Fallback Chain
# ---------------------------------------------------------------------------

def build_llm_chain() -> list[LLMClient]:
    """Constrói a cadeia de provedores na ordem de prioridade (settings).

    Ordem (quality benchmark 2026-07-16): Groq 70B (llama-3.3-70b-versatile,
    qualidade 5.0/5.0, ~2.2s) -> Gemini (gemini-2.5-flash, 5.0/5.0, ~10s) ->
    OpenRouter (conta free limitada: 404/429, mantido por último como fallback
    remoto caso a conta volte a ter crédito) -> Ollama (local).
    """
    settings = get_settings()
    chain: list[LLMClient] = []

    # 1. Groq 70B (primário — free tier, maior qualidade de saída)
    if settings.groq_api_key:
        chain.append(GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        ))

    # 2. Gemini (fallback secundário — mesma qualidade, mais lento)
    if settings.gemini_api_key:
        chain.append(GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        ))

    # 3. OpenRouter (fallback remoto — conta free pode estar limitada)
    if settings.openrouter_api_key:
        chain.append(OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
        ))

    # 4. Ollama (local) - tenta conectar; se falhar, ignora silenciosamente
    # O Ollama não exige chave; só adicionamos se a URL for configurada
    if settings.ollama_base_url:
        # Tenta checar health brevemente
        chain.append(OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        ))

    return chain


class _FallbackLLMClient(LLMClient):
    """Adapter que roteia generate_json/generate_text pela cadeia de fallback.

    Garante que uma falha/quota de um provedor (ex.: 429 do Gemini free tier)
    não derruba o pipeline: ele cai para o próximo disponível da cadeia
    montada por `build_llm_chain` (Groq -> Gemini -> OpenRouter -> Ollama).

    Preserva a assinatura pública de `get_llm_client()` (-> LLMClient) para
    não quebrar `deps.py` nem os agentes que consomem o cliente diretamente.
    """

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return await call_with_fallback(
            system_prompt, user_prompt, json_mode=True
        )

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return await call_with_fallback(
            system_prompt, user_prompt, json_mode=False
        )


async def get_llm_client() -> LLMClient:
    """Retorna um cliente com fallback automático entre os provedores.

    Lazy: só valida a cadeia na chamada. Levanta `LLMError` se nenhum
    provedor estiver configurado (sem chave/URL).
    """
    chain = build_llm_chain()
    if not chain:
        raise LLMError(
            "Nenhum provedor LLM configurado. Defina ao menos uma API key "
            "(OpenRouter, Groq, Gemini) ou Ollama."
        )
    return _FallbackLLMClient()


def build_aux_llm_chain() -> list[LLMClient]:
    """Cadeia de provedores usando o modelo AUXILIAR (barato) de cada um.

    Espelha `build_llm_chain`, mas troca o modelo pelo override configurado
    em settings (`aux_*_model`). Usado pela compressão de artefatos (Fase B1)
    para manter o custo baixo — resumir não precisa do modelo principal caro.
    """
    settings = get_settings()
    chain: list[LLMClient] = []

    if settings.openrouter_api_key:
        chain.append(OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.aux_openrouter_model or settings.openrouter_model,
        ))
    if settings.groq_api_key:
        chain.append(GroqClient(
            api_key=settings.groq_api_key,
            model=settings.aux_groq_model or settings.groq_model,
        ))
    if settings.gemini_api_key:
        chain.append(GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.aux_gemini_model or settings.gemini_model,
        ))
    if settings.ollama_base_url:
        chain.append(OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.aux_ollama_model or settings.ollama_model,
        ))

    return chain


async def call_aux_llm(system_prompt: str, user_prompt: str) -> str:
    """Chama o modelo auxiliar barato (texto), com fallback entre provedores.

    Retorna texto plano (o resumo). Levanta `LLMError` se todos os provedores
    auxiliares falharem — o chamador (compressor) trata isso degradando para o
    texto original em vez de derrubar o pipeline.
    """
    chain = build_aux_llm_chain()
    if not chain:
        raise LLMError("Nenhum provedor LLM auxiliar configurado.")

    last_exc: Exception | None = None
    for idx, client in enumerate(chain):
        try:
            return await client.generate_text(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "aux_llm_provider_failed",
                provider=type(client).__name__,
                attempt=idx + 1,
                error=str(exc),
            )
            continue

    raise LLMError(f"Todos os provedores LLM auxiliares falharam. Último erro: {last_exc}")


async def call_with_fallback(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = True,
) -> dict[str, Any] | str:
    """Tenta cada provedor na cadeia até um funcionar.

    Retorna dict (json_mode=True) ou str (json_mode=False).
    """
    chain = build_llm_chain()
    if not chain:
        raise LLMError("Nenhum provedor LLM configurado.")

    last_exc: Exception | None = None
    for idx, client in enumerate(chain):
        try:
            if json_mode:
                return await client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            else:
                return await client.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "llm_provider_failed",
                provider=type(client).__name__,
                attempt=idx + 1,
                error=str(exc),
            )
            # continua para o próximo
            continue

    raise LLMError(f"Todos os provedores LLM falharam. Último erro: {last_exc}")


async def stream_with_fallback(
    system_prompt: str,
    user_prompt: str,
) -> AsyncGenerator[str, None]:
    """Streaming com fallback: tenta a cadeia e faz yield do primeiro que funciona.

    Se o provedor primário falhar no streaming, recai no texto completo e segue
    pelos próximos da cadeia. Garante que sempre haja ao menos um chunk.
    """
    chain = build_llm_chain()
    if not chain:
        raise LLMError("Nenhum provedor LLM configurado.")

    last_exc: Exception | None = None
    for idx, client in enumerate(chain):
        try:
            async for delta in client.stream_text(
                system_prompt=system_prompt, user_prompt=user_prompt
            ):
                yield delta
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "llm_stream_provider_failed",
                provider=type(client).__name__,
                attempt=idx + 1,
                error=str(exc),
            )
            continue

    raise LLMError(f"Todos os provedores LLM falharam no streaming. Último erro: {last_exc}")