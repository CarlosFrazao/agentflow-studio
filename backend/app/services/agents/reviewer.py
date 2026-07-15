"""Reviewer Agent (F-005, leve): audita consistência Ideia→Pesquisa→Plano.

NÃO reescreve nada — só sinaliza alertas (PRD F-005). Não bloqueia o pipeline:
os alertas aparecem no modal de aprovação e o usuário decide.
"""

from pydantic import BaseModel, Field


class ReviewAlert(BaseModel):
    message: str
    severity: str = "info"  # info | warning | critical


class ReviewOutput(BaseModel):
    alerts: list[ReviewAlert] = Field(default_factory=list)
    critical_count: int = 0
    passed: bool = True
    confidence_score: float = 0.0
    log_summary: str | None = None


_REVIEWER_SYSTEM = (
    "Voce e o Reviewer Agent (leve). Audite a consistencia entre ideia, "
    "pesquisa e plano. Apenas sinalize inconsistencias, nao reescreva. "
    'Responda JSON: {"alerts": [{"message": str, "severity": '
    '"info"|"warning"|"critical"}]}.'
)


class ReviewerAgent:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def run(
        self,
        ideation: dict,
        research: str,
        planner: str,
        code_research: str,
    ) -> ReviewOutput:
        user_prompt = (
            f"IDEATION: {ideation}\nRESEARCH: {research}\n"
            f"PLANNER: {planner}\nCODE_RESEARCH: {code_research}"
        )
        try:
            data = await self._llm.generate_json(
                system_prompt=_REVIEWER_SYSTEM, user_prompt=user_prompt
            )
            alerts = [ReviewAlert(**a) for a in data.get("alerts", [])]
        except Exception:
            alerts = []
        critical = sum(1 for a in alerts if a.severity == "critical")
        log = "; ".join(a.message for a in alerts) if alerts else None
        return ReviewOutput(
            alerts=alerts,
            critical_count=critical,
            passed=critical == 0,
            log_summary=log,
        )
