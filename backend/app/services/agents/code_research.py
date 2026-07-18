"""Code Research Agent (F-008, enxuto): GitHub API + Firecrawl + LLM.

Regras do PRD F-008:
- GitHub API para arquivos de código (LICENSE, README); Firecrawl só p/ externo.
- Nunca copia código automaticamente — apenas sugere (devolve sugestão).
- Classifica licença e avisa quando copyleft (GPL/AGPL).

Wiring (Spec §5): descobre candidatos via GitHub search e enriquece com o
Firecrawl (scrape de docs/blogs fora do GitHub). Se o Firecrawl cair, degrada
para só-GitHub (card informa limitação) — não trava o pipeline.
"""

import re

from pydantic import BaseModel, Field

from app.clients.mcp.firecrawl_client import FirecrawlUnavailableError
from app.core.logging import get_logger
from app.services.learning_memory import LearningMemory

logger = get_logger("code_research_agent")

# Copyleft families matched by word boundary to avoid false positives on
# loose mentions (e.g. "faster than GPL-based tools" in a comparison).
_COPYLEFT = {"GPL", "AGPL", "LGPL"}
_COPYLEFT_RE = re.compile(r"\b(?:GPL|AGPL|LGPL)\b")
# Full-name headers that confirm a real copyleft license.
_COPYLEFT_HEADER_RE = re.compile(
    r"(GENERAL PUBLIC LICENSE|LESSER GENERAL PUBLIC LICENSE|AFFERO GENERAL PUBLIC LICENSE)"
)
# License-context terms that must appear near the acronym to confirm a real
# copyleft license (not a passing mention elsewhere in the text).
_LICENSE_CONTEXT_RE = re.compile(
    r"(?:LICENSE|LICENCE|SPDX|VERSION|\bV\d)", re.IGNORECASE
)
# Window (chars) around the acronym within which a license-context term must
# appear to count as a real copyleft declaration.
_LICENSE_CONTEXT_WINDOW = 40

_CODE_RESEARCH_SYSTEM = (
    "Voce e o Code Research Agent. Dado README + estrutura + licenca de repos "
    "candidatos, sugira arquivos/padroes reutilizaveis. Responda JSON: "
    '{"suggestions": [str], "license_class": "permissive"|"copyleft"|"unknown"}.'
)


class CodeResearchOutput(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
    license_class: str = "unknown"  # permissive | copyleft | unknown
    license_warning: str | None = None
    source_url: str | None = None
    degraded: bool = False  # True quando Firecrawl caiu e usamos só GitHub
    external_docs: list[str] = Field(default_factory=list)


class CodeResearchAgent:
    def __init__(self, llm, github, firecrawl) -> None:
        self._llm = llm
        self._github = github
        self._firecrawl = firecrawl

    async def run(
        self,
        repo_candidates: list[dict] | None = None,
        *,
        query: str = "",
        per_page: int = 5,
        scrape_external: bool = True,
    ) -> CodeResearchOutput:
        """Descobre candidatos (GitHub search) e enriquece com Firecrawl.

        `repo_candidates` pré-computados podem ser passados; caso contrário,
        busca por `query`. O Firecrawl (scrape de docs externos) é opcional e
        degrada para só-GitHub quando indisponível.
        """
        candidates = repo_candidates or []
        if not candidates and query:
            try:
                candidates = await self._github.search_repos(query, per_page=per_page)
            except Exception:
                candidates = []

        if not candidates:
            return CodeResearchOutput()

        candidate = candidates[0]
        repo = candidate.get("full_name", "")

        # 1) GitHub (código/licença — fonte primária, sempre tentada)
        try:
            license_text = await self._github.get_file(repo, "LICENSE")
        except Exception:
            license_text = ""
        license_class = self._classify_license(license_text)
        warning = None
        if license_class == "copyleft":
            warning = "Atencao: licenca copyleft (GPL/AGPL) — reuso exige conformidade."

        try:
            readme = await self._github.get_file(repo, "README.md")
        except Exception:
            readme = ""

        # 2) Firecrawl (docs externos) — opcional, degrada graciosamente
        external_docs: list[str] = []
        degraded = False
        if scrape_external and repo:
            homepage = f"https://github.com/{repo}"
            try:
                result = await self._firecrawl.scrape(homepage)
                content = self._extract_text(result)
                if content:
                    external_docs.append(content)
            except FirecrawlUnavailableError as exc:
                degraded = True
                logger.warning(
                    "code_research_firecrawl_unavailable", repo=repo, error=str(exc)
                )
                # Tarefa B (D2): registra a indisponibilidade na memória de
                # aprendizado (gravação síncrona em thread separada, fail-open).
                try:
                    import asyncio

                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(
                        None,
                        LearningMemory().record_lesson,
                        "code_research",
                        f"Firecrawl indisponível: {exc}",
                    )
                except Exception:
                    pass

        # 3) Síntese via LLM (usa só o que conseguimos coletar)
        try:
            extra = (
                f"\nDOCS_EXTERNOS:\n{chr(10).join(external_docs)}"
                if external_docs
                else ""
            )
            data = await self._llm.generate_json(
                system_prompt=_CODE_RESEARCH_SYSTEM,
                user_prompt=f"repo={repo}\nREADME:\n{readme}\nLICENSE:\n{license_text}{extra}",
            )
            suggestions = data.get("suggestions", [])
        except Exception:
            suggestions = []

        return CodeResearchOutput(
            suggestions=suggestions,
            license_class=license_class,
            license_warning=warning,
            source_url=f"https://github.com/{repo}" if repo else None,
            degraded=degraded,
            external_docs=external_docs,
        )

    @staticmethod
    def _extract_text(result: dict) -> str:
        """Extrai texto útil da resposta do Firecrawl (formato v2)."""
        if not isinstance(result, dict):
            return ""
        data = result.get("data") or result
        if isinstance(data, dict):
            return data.get("markdown") or data.get("content") or ""
        return ""

    @staticmethod
    def _classify_license(text: str) -> str:
        """Classify license as copyleft / permissive / unknown.

        FEAT-005: copyleft detected via word-boundary regex over normalized
        text, so a loose mention of "GPL" in a comparison is not a false
        positive, while real `GPL`/`AGPL`/`LGPL` tokens are.
        """
        upper = text.upper()
        # Real copyleft: full-name header, or the acronym with a license
        # context term nearby (e.g. "GPL-3.0", "GPL version 2"). A loose
        # mention like "faster than GPL-based tools" has no nearby context
        # -> not copyleft.
        #
        # The window is sliced from `upper` (the same string the regex runs
        # on), NOT from `text`. Unicode casing can change length (e.g. the
        # German sharp s "ß" expands to "SS" under .upper()), so indices into
        # `upper` would be misaligned against `text` and silently miss the
        # license-context term. Slicing the matched string keeps indices valid.
        if _COPYLEFT_HEADER_RE.search(upper):
            return "copyleft"
        for match in _COPYLEFT_RE.finditer(upper):
            start, end = match.start(), match.end()
            window = upper[
                max(0, start - _LICENSE_CONTEXT_WINDOW) : end + _LICENSE_CONTEXT_WINDOW
            ]
            if _LICENSE_CONTEXT_RE.search(window):
                return "copyleft"
        if any(k in upper for k in ("MIT", "APACHE", "BSD")):
            return "permissive"
        return "unknown"
