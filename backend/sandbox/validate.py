"""Sandbox de validação de código gerado (container efêmero, sem rede).

PRD F-006 / Spec §3.2: container sem acesso à rede externa nem a env vars do host.
Este módulo é o ponto de entrada usado pelo Dev Agent; em produção roda via
`docker run --rm` (ver sandbox/Dockerfile). Para testes, use um fake.
"""

from dataclasses import dataclass


@dataclass
class SandboxResult:
    success: bool
    stderr: str = ""


class SandboxValidator:
    """Valida código gerado em container efêmero (sem rede)."""

    def __init__(self, image: str = "agentflow-sandbox:latest") -> None:
        self._image = image

    async def validate(self, code: str) -> dict:
        """Executa o código em container isolado e retorna {success, stderr}.

        Implementação real: escreve `code` num arquivo, faz `docker run --rm
        --network none -e DISABLED <image> python /sandbox/code.py`.
        Aqui mantemos o contrato sem acoplar ao Docker nos testes.
        """
        raise NotImplementedError(
            "Sandbox real requer Docker; injete um fake nos testes."
        )
