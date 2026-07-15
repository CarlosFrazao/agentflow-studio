"""Contrato comum de sandbox (Item E — padrão Strategy).

Todo backend de execução (Docker, AWS Lambda, Modal) implementa
`SandboxBackend.validate(code) -> SandboxResult`. O Dev Agent depende
apenas desta abstração, nunca de um provedor concreto.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SandboxResult:
    """Resultado da validação em sandbox."""

    success: bool
    stderr: str = ""
    backend: str = ""


class SandboxBackend(ABC):
    """Estratégia de execução isolada de código gerado."""

    name: str = "base"

    @abstractmethod
    async def validate(self, code: str) -> SandboxResult:
        """Executa `code` em ambiente isolado e retorna o resultado."""
        ...


def get_sandbox_backend(backend: str | None = None) -> SandboxBackend:
    """Factory: seleciona o backend pela configuração (SANDBOX_BACKEND).

    Default 'docker'. Valores desconhecidos caem para Docker (seguro local).
    """
    from app.core.config import get_settings

    settings = get_settings()
    kind = (backend or settings.sandbox_backend or "docker").lower()

    if kind == "aws":
        from app.sandbox.aws_sandbox import AWSLambdaSandbox

        return AWSLambdaSandbox()
    if kind == "modal":
        from app.sandbox.modal_sandbox import ModalSandbox

        return ModalSandbox()
    # default / fallback
    from app.sandbox.docker_sandbox import DockerSandbox

    return DockerSandbox()
