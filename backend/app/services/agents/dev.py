"""Dev Agent (F-006): gera código e valida em sandbox antes de entregar.

PRD F-006: após gerar, tenta executar em container efêmero (sem rede) e corrige
até 2 tentativas. O sandbox é injetável (testável sem Docker de verdade).
"""

from pydantic import BaseModel


class DevOutput(BaseModel):
    code: str = ""
    ran_in_sandbox: bool = False
    sandbox_success: bool = False
    attempts: int = 0
    error_log: str | None = None


_DEV_SYSTEM = (
    "Voce e o Dev Agent. Gere o codigo para o plano fornecido. "
    "Responda APENAS com o codigo (sem markdown fences extras)."
)


class DevAgent:
    def __init__(self, llm, sandbox) -> None:
        self._llm = llm
        self._sandbox = sandbox
        self._max_attempts = 2

    async def run(self, plan: str) -> DevOutput:
        last_error: str | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                code = await self._llm.generate_text(
                    system_prompt=_DEV_SYSTEM, user_prompt=plan
                )
            except Exception as exc:
                return DevOutput(attempts=attempt, error_log=str(exc))

            result = await self._sandbox.validate(code)
            if result.success:
                return DevOutput(
                    code=code,
                    ran_in_sandbox=True,
                    sandbox_success=True,
                    attempts=attempt,
                )
            last_error = result.stderr or "erro desconhecido"

        # Esgotou tentativas: entrega com aviso (PRD F-006)
        return DevOutput(
            code=code,
            ran_in_sandbox=True,
            sandbox_success=False,
            attempts=self._max_attempts,
            error_log=last_error,
        )
