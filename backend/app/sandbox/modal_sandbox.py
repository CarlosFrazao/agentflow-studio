"""Backend de sandbox via Modal (Item E — extensível/multicloud).

Usa o SDK `modal` (lazy import) para executar o código em um sandbox
efêmero na nuvem Modal. Falha graciosamente se o SDK ou as credenciais
estiverem ausentes.
"""

from app.core.logging import get_logger
from app.core.responses import sanitize_error
from app.sandbox.base import SandboxBackend, SandboxResult

logger = get_logger("modal_sandbox")


class ModalSandbox(SandboxBackend):
    """Executa código em um Modal sandbox sem acesso de rede.

    `network_access=False` no `@app.function` bloqueia tráfego de saída,
    equivalente a `--network none` do Docker (B7-2).
    """

    name = "modal"

    async def validate(self, code: str) -> SandboxResult:
        try:
            import modal
        except ImportError:
            return SandboxResult(
                success=False,
                stderr="modal not installed",
                backend=self.name,
            )
        try:
            image = modal.Image.debian_slim().pip_install("pytest")
            app = modal.App.lookup("agentflow-sandbox", create_if_missing=True)

            @app.function(
                image=image,
                # Defense-in-depth: `network_access=False` blocks outbound
                # network from the sandbox container, equivalent to docker's
                # `--network none`. Generated code cannot exfiltrate data or
                # reach internal services (B7-2).
                network_access=False,
            )
            async def _run(src: str) -> dict:
                import subprocess
                import tempfile
                from pathlib import Path

                with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
                    f.write(src)
                    path = Path(f.name)
                    proc = subprocess.run(
                        ["python", str(path)], capture_output=True, text=True
                    )
                return {"success": proc.returncode == 0, "stderr": proc.stderr}

            result = await _run.remote.aio(code)
            return SandboxResult(
                success=bool(result.get("success", False)),
                stderr=result.get("stderr", ""),
                backend=self.name,
            )
        except Exception as exc:  # noqa: BLE001 - degrada em falha de infra
            logger.warning("modal_sandbox_failed", error=str(exc))
            return SandboxResult(
                success=False, stderr=sanitize_error(exc), backend=self.name
            )
