"""Testes unitários do Dev Agent (F-006) — correção do pipeline.

Cobrem:
- Problema 3: o Dev Agent recebe o plano REAL (não a string fixa "plano") e
  usa o sandbox real (injétável, não o _NoopSandbox removido).
- Problema 4: a autocorreção é DIRECIONADA — a 2ª tentativa inclui o código
  anterior e o stderr do sandbox no prompt, em vez de regerar do zero.
"""

import pytest

from app.sandbox.base import SandboxBackend, SandboxResult
from app.services.agents.dev import DevAgent, DevOutput
from app.services.llm import LLMClient


class _RecordingLLM(LLMClient):
    """LLM fake que grava os system_prompts/user_prompts recebidos."""

    def __init__(self, code: str = "print('ok')") -> None:
        self._code = code
        self.system_prompts: list[str] = []
        self.user_prompts: list[str] = []

    async def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.system_prompts.append(system_prompt)
        self.user_prompts.append(user_prompt)
        return {}

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        self.system_prompts.append(system_prompt)
        self.user_prompts.append(user_prompt)
        return self._code


class _ScriptedSandbox(SandboxBackend):
    """Sandbox fake que falha com stderr nas N primeiras tentativas."""

    name = "scripted"

    def __init__(self, fail_times: int = 0, stderr: str = "SyntaxError: bad") -> None:
        self._fail_times = fail_times
        self._stderr = stderr
        self.calls = 0

    async def validate(self, code: str) -> SandboxResult:
        self.calls += 1
        if self.calls <= self._fail_times:
            return SandboxResult(success=False, stderr=self._stderr, backend=self.name)
        return SandboxResult(success=True, stderr="", backend=self.name)


async def test_dev_uses_real_plan_and_real_sandbox() -> None:
    """Problema 3: plano real passado + sandbox injetado (não _NoopSandbox)."""
    llm = _RecordingLLM(code="print(1)")
    sandbox = _ScriptedSandbox()
    agent = DevAgent(llm=llm, sandbox=sandbox)

    out = await agent.run("PLANO_REAL_123")

    assert out.attempts == 1
    assert out.sandbox_success is True
    # O plano real foi repassado ao LLM (1ª tentativa).
    assert llm.user_prompts[0] == "PLANO_REAL_123"
    # O sandbox REAL injetado foi executado (não o _NoopSandbox removido).
    assert sandbox.calls == 1


async def test_dev_retry_includes_stderr_and_previous_code() -> None:
    """Problema 4: a 2ª tentativa recebe o stderr + código anterior no prompt."""
    stderr = "Traceback: NameError: x is not defined"
    llm = _RecordingLLM(code="print(x)")
    sandbox = _ScriptedSandbox(fail_times=1, stderr=stderr)
    agent = DevAgent(llm=llm, sandbox=sandbox)

    out = await agent.run("PLANO_BASE")

    # Duas chamadas ao LLM: 1ª geração + 1ª autocorreção direcionada.
    assert len(llm.system_prompts) == 2
    assert out.attempts == 2
    assert out.sandbox_success is True

    second_sys = llm.system_prompts[1]
    # O prompt de retry contém o erro e o código anterior (§6.5 dos Prompts).
    assert stderr in second_sys
    assert "print(x)" in second_sys  # previous_code
    assert "autocorrecao" in second_sys.lower()

    # A 1ª tentativa NÃO é o prompt de autocorreção.
    assert "autocorrecao" not in llm.system_prompts[0].lower()


async def test_dev_exhausts_attempts_and_reports_error() -> None:
    """Falha persistente: entrega com aviso e loga o stderr da última tentativa."""
    stderr = "IndentationError: unexpected indent"
    llm = _RecordingLLM(code="def f(:")
    sandbox = _ScriptedSandbox(fail_times=99, stderr=stderr)
    agent = DevAgent(llm=llm, sandbox=sandbox)

    out = await agent.run("PLANO_BASE")
    assert out.attempts == 2
    assert out.sandbox_success is False
    assert out.error_log == stderr
