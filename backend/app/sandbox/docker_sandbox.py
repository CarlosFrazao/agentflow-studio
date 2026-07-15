"""Backend de sandbox via Docker local (Item E).

Executa o código gerado em container efêmero, sem rede e sem acesso a
env vars do host (PRD F-006 / Spec §3.2). Em produção usa a imagem
`agentflow-sandbox:latest` construída pelo sandbox/Dockerfile.
"""

import asyncio
from pathlib import Path
from typing import Optional

from app.sandbox.base import SandboxBackend, SandboxResult


class DockerSandbox(SandboxBackend):
    """Valida código em container Docker efêmero."""

    name = "docker"

    def __init__(self, image: str = "agentflow-sandbox:latest") -> None:
        self._image = image

    async def validate(self, code: str) -> SandboxResult:
        """Escreve o código num arquivo temporário e roda `docker run --rm`.

        `--network none` garante isolamento de rede; `-e DISABLED` impede
        leitura de env vars do host. Retorna {success, stderr}.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False
        ) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)

        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "-e", "DISABLED",
            "-v", f"{tmp_path}:/sandbox/code.py:ro",
            self._image,
            "python", "/sandbox/code.py",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _out, err = await proc.communicate()
            stderr = err.decode("utf-8", errors="replace") if err else ""
            return SandboxResult(
                success=proc.returncode == 0,
                stderr=stderr,
                backend=self.name,
            )
        except FileNotFoundError:
            # docker não instalado no ambiente
            return SandboxResult(
                success=False,
                stderr="docker executable not found",
                backend=self.name,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
