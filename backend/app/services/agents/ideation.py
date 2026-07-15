"""Ideation Agent (F-002): ideia bruta -> JSON estruturado de projeto.

Recebe texto livre do usuário e produz a estrutura que o Research Agent
consumirá (project_name, key_features, elevator_pitch) + confidence_score.
"""

from pydantic import BaseModel, Field

from app.services.llm import LLMClient


class IdeationOutput(BaseModel):
    project_name: str
    key_features: list[str] = Field(default_factory=list)
    elevator_pitch: str = ""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


_IDEATION_SYSTEM = (
    "Voce e o Ideation Agent do AgentFlow Studio. Transforme a ideia bruta "
    "do usuario em um JSON estruturado. Responda APENAS em JSON com o schema: "
    '{"project_name": str, "key_features": [str], "elevator_pitch": str, '
    '"confidence_score": float entre 0 e 1}.'
)


class IdeationAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(self, raw_idea: str) -> IdeationOutput:
        data = await self._llm.generate_json(
            system_prompt=_IDEATION_SYSTEM, user_prompt=raw_idea
        )
        return IdeationOutput(
            project_name=data.get("project_name", "Projeto sem nome"),
            key_features=data.get("key_features", []),
            elevator_pitch=data.get("elevator_pitch", ""),
            confidence_score=float(data.get("confidence_score", 0.0)),
        )
