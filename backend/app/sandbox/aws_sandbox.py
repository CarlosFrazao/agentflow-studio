"""Backend de sandbox via AWS Lambda (Item E — extensível/multicloud).

Usa boto3 (lazy import) para invocar uma função Lambda pré-provisionada
que executa o código em isolamento. Se boto3 ou as credenciais ausentes,
falha graciosamente com SandboxResult(success=False) em vez de quebrar o app.
"""

from app.core.logging import get_logger
from app.sandbox.base import SandboxBackend, SandboxResult

logger = get_logger("aws_sandbox")


class AWSLambdaSandbox(SandboxBackend):
    """Executa código em uma AWS Lambda de sandbox."""

    name = "aws"

    def __init__(self, function_name: str = "agentflow-sandbox") -> None:
        self._function_name = function_name

    async def validate(self, code: str) -> SandboxResult:
        try:
            import json

            import boto3
        except ImportError:
            return SandboxResult(
                success=False,
                stderr="boto3 not installed",
                backend=self.name,
            )
        try:
            client = boto3.client("lambda")
            resp = client.invoke(
                FunctionName=self._function_name,
                Payload=json.dumps({"code": code}).encode(),
            )
            import json as _json

            payload = _json.loads(resp["Payload"].read())
            return SandboxResult(
                success=bool(payload.get("success", False)),
                stderr=payload.get("stderr", ""),
                backend=self.name,
            )
        except Exception as exc:  # noqa: BLE001 - falha de infra deve degradar
            logger.warning("aws_sandbox_failed", error=str(exc))
            return SandboxResult(success=False, stderr=str(exc), backend=self.name)
