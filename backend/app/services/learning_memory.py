"""Memória de aprendizado incremental (Fase D2 / F-013 de inteligência).

Grava e recupera "lições" aprendidas entre execuções dos agentes (ex.:
"Firecrawl caiu na porta 3022", "SRA demora > 90s em modo cirurgia") e as
injeta no prompt do agente correspondente via ``inject_context`` (Fase B2).

Persistência **síncrona** em markdown local (``backend/data/agent_lessons.md``),
uma lição por linha no formato::

    - [<agent>] <lesson> <!-- ts=<iso8601> -->

A escolha por markdown local (em vez de tabela) mantém a memória legível por
humanos, versionável e independente do event loop async — ``inject_context``
roda de forma síncrona sob o loop ativo do FastAPI e não pode abrir uma sessão
SQLAlchemy async concorrente.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger("learning_memory")

# backend/app/services/learning_memory.py -> parents[2] = backend/
LESSONS_PATH: Path = Path(__file__).resolve().parents[2] / "data" / "agent_lessons.md"

# Formato de linha: "- [agent] lesson <!-- ts=... -->"
_LINE_RE = re.compile(
    r"^- \[(?P<agent>[^\]]+)\]\s(?P<lesson>.*?)(?:\s*<!-- ts=(?P<ts>[^>]*?) -->)?$"
)

# Serializa escritas concorrentes ao arquivo dentro do mesmo processo.
_WRITE_LOCK = threading.Lock()


def _normalize_agent(agent: str) -> str:
    return agent.strip().lower()


def _flatten(text: str) -> str:
    """Achata quebras de linha e espaços redundantes (uma lição por linha)."""
    return re.sub(r"\s+", " ", text).strip()


class LearningMemory:
    """Camada de memória append-only de lições por agente."""

    def __init__(self, path: Path | None = None) -> None:
        # ``None`` resolve para o LESSONS_PATH atual no momento da chamada
        # (permite monkeypatch do módulo nos testes).
        self._path = path

    @property
    def path(self) -> Path:
        return self._path if self._path is not None else LESSONS_PATH

    def record_lesson(self, agent: str, lesson: str) -> None:
        """Grava uma lição para ``agent`` (append seguro, UTF-8).

        Levanta ``ValueError`` se o agente ou a lição forem vazios.
        """
        agent_norm = _normalize_agent(agent)
        lesson_flat = _flatten(lesson)
        if not agent_norm:
            raise ValueError("agent não pode ser vazio")
        if not lesson_flat:
            raise ValueError("lesson não pode ser vazio")

        timestamp = datetime.now(tz=timezone.utc).isoformat()
        line = f"- [{agent_norm}] {lesson_flat} <!-- ts={timestamp} -->\n"

        path = self.path
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        logger.info("lesson_recorded", agent=agent_norm)

    def recall_lessons(self, agent: str, k: int = 5) -> list[str]:
        """Retorna as últimas ``k`` lições registradas para ``agent``.

        Ordem cronológica (mais antiga -> mais recente). Se o arquivo não
        existir ou não houver lições para o agente, retorna lista vazia.
        """
        if k <= 0:
            return []
        agent_norm = _normalize_agent(agent)
        path = self.path
        if not agent_norm or not path.exists():
            return []

        matched: list[str] = []
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                if not line.startswith("- ["):
                    continue
                m = _LINE_RE.match(line)
                if m is None:
                    continue
                if _normalize_agent(m.group("agent")) != agent_norm:
                    continue
                lesson = m.group("lesson").strip()
                if lesson:
                    matched.append(lesson)

        return matched[-k:]


def get_lessons_for_card(card: Any, k: int = 5) -> list[str]:
    """Extrai o agente do ``card`` e recupera suas lições aprendidas.

    O agente é resolvido por (nesta ordem):
      1. ``card.meta["agent"]`` (agente explicitamente anotado no card);
      2. ``next_agent_for_column(card.column)`` (agente da coluna atual).

    Retorna lista vazia se o agente não puder ser determinado ou não houver
    lições — nunca levanta (uso em ``inject_context``, fail-open).
    """
    agent = _resolve_agent(card)
    if not agent:
        return []
    return LearningMemory().recall_lessons(agent, k=k)


def _resolve_agent(card: Any) -> str | None:
    """Deriva o nome do agente do card (meta.agent ou coluna)."""
    meta = getattr(card, "meta", None)
    if isinstance(meta, dict):
        meta_agent = meta.get("agent")
        if isinstance(meta_agent, str) and meta_agent.strip():
            return _normalize_agent(meta_agent)

    column = getattr(card, "column", None)
    if isinstance(column, str) and column.strip():
        # Import local para evitar ciclo (orchestrator importa este módulo de
        # forma lazy em inject_context).
        from app.services.orchestrator import next_agent_for_column

        try:
            agent = next_agent_for_column(column)
        except ValueError:
            logger.debug("resolve_agent_invalid_column", column=column)
            return None
        if agent:
            return _normalize_agent(agent)

    return None
