"""Research Agent (F-003): delega ao SRA e orquestra Code Research.

Se o SRA estiver indisponível, degrada graciosamente (PRD F-003): retorna
relatório vazio + flag `degraded` + aviso, sem travar o pipeline.
"""

from pydantic import BaseModel

import asyncio

from app.services.llm import LLMClient
from app.services.learning_memory import LearningMemory


class ResearchOutput(BaseModel):
    sra_report: str = ""
    confidence: float = 0.0
    degraded: bool = False
    warning: str = ""


_RESEARCH_SYSTEM = (
    "Voce e o Research Agent. Sintetize o relatorio de mercado do SRA em JSON: "
    '{"synthesis": str, "competitors": [str], "gaps": [str], "confidence": float}.'
)


class ResearchAgent:
    def __init__(self, llm: LLMClient, sra) -> None:
        self._llm = llm
        self._sra = sra

    async def run(self, query: str, mode: str = "guerrilha") -> ResearchOutput:
        try:
            sra_report = await self._sra.research(query, mode)
        except Exception as exc:
            # Tarefa B (D2): registra a indisponibilidade na memória de
            # aprendizado (gravação síncrona em thread separada, fail-open).
            try:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(
                    None,
                    LearningMemory().record_lesson,
                    "research",
                    f"SRA indisponível: {exc}",
                )
            except Exception:
                pass
            return ResearchOutput(
                degraded=True,
                warning="pesquisa de mercado incompleta (SRA indisponivel)",
            )
        try:
            data = await self._llm.generate_json(
                system_prompt=_RESEARCH_SYSTEM, user_prompt=sra_report
            )
        except Exception:
            # mesmo sem LLM, preserva o relatorio bruto do SRA
            return ResearchOutput(sra_report=sra_report)
        return ResearchOutput(
            sra_report=sra_report, confidence=float(data.get("confidence", 0.0))
        )
