"""Validação do DockerSandbox real (Problema 3b / Regra 4 do prompt).

Confirma que o DockerSandbox (backend padrão do Dev Agent) realmente executa e
captura erros de código quando a imagem `agentflow-sandbox:latest` existe.

O teste é PULADO se o Docker ou a imagem não estiverem disponíveis no ambiente
(não deve quebrar a suíte onde o Docker não roda). A presença da imagem é
verificada via `docker image inspect` antes de tentar validar de verdade.
"""

import pytest

from app.sandbox.docker_sandbox import DockerSandbox

pytestmark = pytest.mark.asyncio

_IMAGE = "agentflow-sandbox:latest"


def _image_present() -> bool:
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        return False
    proc = subprocess.run(
        ["docker", "image", "inspect", _IMAGE],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


@pytest.mark.skipif(not _image_present(), reason="Docker ou imagem agentflow-sandbox:latest ausente")
async def test_docker_sandbox_accepts_valid_code() -> None:
    """Código válido roda e o sandbox reporta success=True."""
    sb = DockerSandbox()
    result = await sb.validate('print("ok")')
    assert result.success is True
    assert result.stderr == ""


@pytest.mark.skipif(not _image_present(), reason="Docker ou imagem agentflow-sandbox:latest ausente")
async def test_docker_sandbox_captures_broken_code() -> None:
    """Código quebrado de propósito é capturado (success=False + stderr)."""
    sb = DockerSandbox()
    result = await sb.validate('print("unclosed')
    assert result.success is False
    assert "SyntaxError" in result.stderr
