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

_DEV_RETRY_SYSTEM = (
    "Voce e o Dev Agent do AgentFlow Studio em modo de autocorrecao. "
    "O codigo que voce gerou anteriormente falhou ao rodar no sandbox de "
    "validacao. Esta e a tentativa {attempt_number} de no maximo 2.\n\n"
    "ERRO REPORTADO PELO SANDBOX:\n{stderr}\n\n"
    "CODIGO ANTERIOR:\n{previous_code}\n\n"
    "REGRAS:\n"
    "1. Diagnostique a causa raiz do erro antes de corrigir.\n"
    "2. Corrija apenas o necessario; nao reescreva o que nao tem relacao "
    "com o erro.\n"
    "3. Se esta for a tentativa 2 e voce nao tiver certeza da causa raiz, "
    "seja honesto e mantenha o que funciona.\n"
    "4. Responda APENAS com o codigo corrigido (sem markdown fences extras)."
)


class DevAgent:
    def __init__(self, llm, sandbox) -> None:
        self._llm = llm
        self._sandbox = sandbox
        self._max_attempts = 2

    async def run(self, plan: str) -> DevOutput:
        last_error: str | None = None
        previous_code: str = ""
        for attempt in range(1, self._max_attempts + 1):
            try:
                if attempt == 1:
                    # Primeira tentativa: gera a partir do plano.
                    code = await self._llm.generate_text(
                        system_prompt=_DEV_SYSTEM, user_prompt=plan
                    )
                else:
                    # Tentativas seguintes: autocorrecao DIRECIONADA — inclui o
                    # codigo anterior e o stderr do sandbox, pedindo a correcao
                    # do erro (nao uma geracao do zero). Ref: Prompts v0.1 §6.5.
                    system = _DEV_RETRY_SYSTEM.format(
                        attempt_number=attempt,
                        stderr=last_error or "erro desconhecido",
                        previous_code=previous_code,
                    )
                    code = await self._llm.generate_text(
                        system_prompt=system, user_prompt=plan
                    )
            except Exception as exc:
                return DevOutput(attempts=attempt, error_log=str(exc))

            previous_code = code
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
