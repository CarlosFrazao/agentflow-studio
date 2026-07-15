"""Testes TDD dos backends de sandbox (Item E do analise_omnigent.md).

Valida o padrão Strategy: um contrato comum e múltiplas implementações
(Docker, AWS Lambda, Modal) selecionadas por configuração, sem acoplar
o Dev Agent a um provedor específico.
"""

import pytest

from app.sandbox.base import SandboxBackend, SandboxResult, get_sandbox_backend
from app.sandbox.docker_sandbox import DockerSandbox
from app.sandbox.aws_sandbox import AWSLambdaSandbox
from app.sandbox.modal_sandbox import ModalSandbox

pytestmark = pytest.mark.asyncio


class FakeSandboxBackend(SandboxBackend):
    """Backend falso para testar o factory e o Dev Agent sem rede."""

    def __init__(self, name: str = "fake", ok: bool = True) -> None:
        self.name = name
        self.ok = ok
        self.last_code: str | None = None

    async def validate(self, code: str) -> SandboxResult:
        self.last_code = code
        return SandboxResult(success=self.ok, stderr="" if self.ok else "erro simulado")


async def test_factory_returns_docker_by_default(monkeypatch) -> None:
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "sandbox_backend", "docker")
    backend = get_sandbox_backend()
    assert isinstance(backend, DockerSandbox)


async def test_factory_returns_aws(monkeypatch) -> None:
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "sandbox_backend", "aws")
    backend = get_sandbox_backend()
    assert isinstance(backend, AWSLambdaSandbox)


async def test_factory_returns_modal(monkeypatch) -> None:
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "sandbox_backend", "modal")
    backend = get_sandbox_backend()
    assert isinstance(backend, ModalSandbox)


async def test_factory_unknown_backend_falls_back_to_docker(monkeypatch) -> None:
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "sandbox_backend", "inexistente")
    backend = get_sandbox_backend()
    assert isinstance(backend, DockerSandbox)


async def test_fake_backend_validate_contract() -> None:
    fake = FakeSandboxBackend(ok=True)
    result = await fake.validate("print(1)")
    assert result.success is True
    assert fake.last_code == "print(1)"
