"""Planner Agent (F-004): plano técnico a partir de Ideation + Research + Code Research.

O input inclui o output do Research Agent e do Code Research Agent (PRD F-004
adição): a stack recomendada leva em conta padrões identificados pelo Code Research.
"""

from pydantic import BaseModel, Field


class PlannerOutput(BaseModel):
    title: str = ""
    stack: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    raw_plan: str = ""


_PLANNER_SYSTEM = (
    "Voce e o Planner Agent. Elabore o plano tecnico. Responda JSON: "
    '{"title": str, "stack": [str], "milestones": [str], "risks": [str]}. '
    "Leve em conta os padroes sugeridos pelo Code Research Agent na stack."
)


class PlannerAgent:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def run(
        self,
        ideation: dict,
        research: str,
        code_research: str,
    ) -> PlannerOutput:
        user_prompt = (
            f"IDEATION: {ideation}\nRESEARCH: {research}\n"
            f"CODE_RESEARCH: {code_research}"
        )
        try:
            data = await self._llm.generate_json(
                system_prompt=_PLANNER_SYSTEM, user_prompt=user_prompt
            )
        except Exception:
            return PlannerOutput(raw_plan=user_prompt)
        return PlannerOutput(
            title=data.get("title", ideation.get("project_name", "")),
            stack=data.get("stack", []),
            milestones=data.get("milestones", []),
            risks=data.get("risks", []),
            raw_plan=user_prompt,
        )
