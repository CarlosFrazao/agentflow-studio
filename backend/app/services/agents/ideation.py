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
    problem_statement: str = ""
    target_user: str = ""
    out_of_scope: str = ""
    open_questions: list[str] = Field(default_factory=list)

    @property
    def needs_clarification(self) -> bool:
        """Sinal derivado (single source of truth): há perguntas em aberto?

        NÃO vem do LLM — é sempre computado a partir de `open_questions`, para
        evitar que o modelo declare o card como "claro" tendo perguntas pendentes.
        """
        return bool(self.open_questions)


_IDEATION_SYSTEM = (
    "Voce e o Ideation Agent do AgentFlow Studio. Transforme a ideia bruta "
    "do usuario em um JSON estruturado. Responda APENAS em JSON com o schema: "
    '{"project_name": str, "key_features": [str], "elevator_pitch": str, '
    '"confidence_score": float entre 0 e 1, "problem_statement": str, '
    '"target_user": str, "out_of_scope": str, "open_questions": [str]}. '
    "Se a ideia for vaga ou contraditoria, popule `open_questions` com perguntas "
    "especificas em vez de inventar detalhes."
)


class IdeationAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(self, raw_idea: str) -> IdeationOutput:
        data = await self._llm.generate_json(
            system_prompt=_IDEATION_SYSTEM, user_prompt=raw_idea
        )
        # FREE-TIER ROBUSTNESS: weak models (e.g. gemma free) sometimes omit
        # `project_name` (or return empty/whitespace). Never surface the useless
        # "Projeto sem nome" placeholder to the chat — derive a readable name
        # from the user's own words instead. Preserves a valid LLM name when given.
        llm_name = (data.get("project_name") or "").strip()
        project_name = llm_name if llm_name else _derive_name(raw_idea)
        return IdeationOutput(
            project_name=project_name,
            key_features=data.get("key_features", []),
            elevator_pitch=data.get("elevator_pitch", ""),
            confidence_score=float(data.get("confidence_score", 0.0)),
            problem_statement=data.get("problem_statement", ""),
            target_user=data.get("target_user", ""),
            out_of_scope=data.get("out_of_scope", ""),
            open_questions=data.get("open_questions") or [],
        )


# Words stripped from the START of the raw idea (one at a time, left-to-right)
# to reach the actual product description. Includes intent verbs ("quero",
# "criar") and the generic product nouns ("app", "site", "de").
_INTENT_LEADING_WORDS = {
    "quero",
    "criar",
    "fazer",
    "tenho",
    "gostaria",
    "preciso",
    "quer",
    "queria",
    "um",
    "uma",
    "uns",
    "umas",
    "app",
    "site",
    "sistema",
    "system",
    "plataforma",
    "plataform",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "para",
    "i",
    "want",
    "to",
    "build",
    "an",
    "a",
    "the",
    "of",
    "for",
}

_GENERIC_NOUNS = {"app", "site", "sistema", "system", "plataforma", "plataform"}


def _strip_intent_prefix(raw_idea: str) -> str:
    """Drop leading intent words ("quero criar um app de") from the raw idea.

    Iterates left-to-right removing known leading words until the first content
    word. Stops at the first word NOT in the intent set, so we never eat into
    the actual product description.
    """
    words = raw_idea.strip().split()
    idx = 0
    while idx < len(words) and words[idx].lower() in _INTENT_LEADING_WORDS:
        idx += 1
    return " ".join(words[idx:]).strip()


def _derive_name(raw_idea: str) -> str:
    """Build a readable project name from the user's raw idea.

    Strategy (grammar-preserving): strip leading intent words ("quero criar um
    app de") so the remaining words — including prepositions like "para"/"com"/
    "de" — stay fluent ("App de Caronas para a faculdade"). A lone bare noun
    ("caronas") gets an "App de" prefix. Falls back to a neutral label when the
    idea is empty or all-stopwords.
    """
    if not raw_idea or not raw_idea.strip():
        return "Novo Projeto"

    stripped = _strip_intent_prefix(raw_idea)
    if not stripped:
        # Only intent/stopwords were present — use the raw idea, sentence-cased.
        return raw_idea.strip().capitalize()

    words = stripped.split()
    # Gentle sentence-case: only the first letter is upper-cased, keeping
    # mid-sentence prepositions lowercase (.title() would wrongly cap every word).
    phrase = stripped[0].upper() + stripped[1:]

    # A single bare noun reads as incomplete -> prefix with product type.
    if len(words) == 1:
        return f"App de {phrase}"
    # If the original idea named a generic product type ("app"/"site"/
    # "sistema") that we stripped as an intent word, re-introduce it so the name
    # stays explicit ("App de Caronas para a faculdade").
    had_generic = any(w.lower() in _GENERIC_NOUNS for w in raw_idea.lower().split())
    if had_generic and not any(w.lower() in _GENERIC_NOUNS for w in words):
        return f"App de {phrase}"
    return phrase
