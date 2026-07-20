"""Grafo de preferências aprendidas (Fase D1 / F-010).

Lê e escreve a tabela ``user_preferences`` (SQLAlchemy) para montar um grafo
"aprendizado visível" a partir das preferências confirmadas do usuário.

O grafo transforma preferências confirmadas (``confidence_count >= 2``) em
nós:

- **nós** = preferências (uma por combinação ``attribute``/``value``),
- **arestas** = sobreposição lexical entre os ``values`` + co-ocorrência do
  mesmo ``attribute`` em valores distintos.

A mutação ``remove`` apenas **arquiva** a preferência (``archived=True``),
mantendo o histórico físico recuperável. ``restore`` reverte o arquivamento.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.user_preference import UserPreference

logger = get_logger("preference_graph")

APPLY_THRESHOLD = 2
TOKEN_MIN_LEN = 3


def _tokenize(text: str) -> set[str]:
    """Normaliza e extrai tokens de comprimento útil."""
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= TOKEN_MIN_LEN}


def _overlap_score(tokens_a: set[str], tokens_b: set[str]) -> int:
    """Sobrecarga lexical: quantos tokens em comum (mínimo 1 para ligar)."""
    if not tokens_a or not tokens_b:
        return 0
    return len(tokens_a & tokens_b)


def _build_pref_nodes(prefs: list[UserPreference]) -> list[dict[str, Any]]:
    """Converte preferências confirmadas em nós de grafo."""
    nodes: list[dict[str, Any]] = []
    for p in prefs:
        nodes.append(
            {
                "id": str(p.id),
                "label": p.value,
                "kind": "preference",
                "attribute": p.attribute,
                "value": p.value,
                "confidenceCount": p.confidence_count,
                "archived": p.archived,
                "lastReinforcedAt": p.last_reinforced_at,
            }
        )
    return nodes


def _build_edges(prefs: list[UserPreference]) -> list[dict[str, Any]]:
    """Arestas por sobreposição lexical entre valores + co-ocorrência de atributo.

    Duas preferências se ligam quando compartilham tokens lexicais no ``value``
    (similaridade de intenção) ou quando pertencem ao mesmo ``attribute`` com
    valores distintos (co-ocorrência de preferência).
    """
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    meta = [(str(p.id), p.attribute, p.value, _tokenize(p.value)) for p in prefs]
    for i in range(len(meta)):
        id_a, attr_a, val_a, tok_a = meta[i]
        for j in range(i + 1, len(meta)):
            id_b, attr_b, val_b, tok_b = meta[j]
            lexical = _overlap_score(tok_a, tok_b)
            co_occur = 1 if (attr_a == attr_b and val_a != val_b) else 0
            weight = lexical + co_occur
            if weight <= 0:
                continue
            key = tuple(sorted((id_a, id_b)))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "source": id_a,
                    "target": id_b,
                    "weight": weight,
                    "kind": "lexical" if lexical >= co_occur else "co_occurrence",
                }
            )
    return edges


def density_stats(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Estatísticas de densidade do grafo."""
    linked: set[str] = set()
    for e in edges:
        linked.add(e["source"])
        linked.add(e["target"])
    n = len(nodes)
    if n == 0:
        return {
            "nodes": 0,
            "edges": len(edges),
            "edges_per_node": 0.0,
            "linked_nodes": 0,
            "isolated_pct": 0.0,
            "applied_nodes": 0,
            "archived_nodes": 0,
        }
    return {
        "nodes": n,
        "edges": len(edges),
        "edges_per_node": round(len(edges) / n, 3),
        "linked_nodes": len(linked),
        "isolated_pct": round(100 * (n - len(linked)) / n, 1),
        "applied_nodes": sum(
            1 for x in nodes if x["confidenceCount"] >= APPLY_THRESHOLD
        ),
        "archived_nodes": sum(1 for x in nodes if x["archived"]),
    }


async def build_graph(db_session: AsyncSession, *, user_id=None) -> dict[str, Any]:
    """Monta o grafo de preferências a partir de ``user_preferences`` reais.

    Por padrão usa TODAS as preferências (grafo global). Se ``user_id`` for
    passado, filtra pelo dono. Nós = preferências; arestas = co-ocorrência +
    sobreposição lexical.
    """
    stmt = select(UserPreference)
    if user_id is not None:
        stmt = stmt.where(UserPreference.user_id == user_id)
    prefs = (await db_session.scalars(stmt)).all()

    nodes = _build_pref_nodes(prefs)
    edges = _build_edges(prefs)

    stats = density_stats(nodes, edges)
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
    }


async def mutate_preference(
    db_session: AsyncSession,
    preference_id: str,
    action: str,
    *,
    value: str | None = None,
    user_id: UUID | str | None = None,
) -> UserPreference:
    """Edita ou remove (arquiva recuperável) uma preferência.

    - ``edit``   : reescreve ``value`` (mantém histórico de reforço).
    - ``remove`` : arquiva (``archived=True``) — não apaga o histórico físico;
      restaure com ``action="restore"``.

    Defense-in-depth (FEAT-001 / B9-3): quando ``user_id`` é informado, a
    preferência só é mutada se ``pref.user_id`` coincidir; caso contrário levanta
    ``NotFoundError`` (não vaza a existência do recurso de terceiros — anti-IDOR).

    Levanta ``NotFoundError`` se a preferência não existir.
    """
    pref = await db_session.get(UserPreference, _coerce_uuid(preference_id))
    if pref is None:
        raise NotFoundError("UserPreference", preference_id)

    if user_id is not None and UUID(str(pref.user_id)) != UUID(str(user_id)):
        logger.warning(
            "preference_owner_mismatch",
            id=str(pref.id),
            expected=str(user_id),
            actual=str(pref.user_id),
        )
        raise NotFoundError("UserPreference", preference_id)

    action = action.lower()
    if action == "edit":
        if not value or not value.strip():
            raise ValidationError("edit requer um 'value' não vazio")
        pref.value = value.strip()
        pref.confidence_count = max(pref.confidence_count, 1)
        logger.info("preference_edited", id=str(pref.id), attribute=pref.attribute)
    elif action == "remove":
        pref.archived = True
        logger.info("preference_archived", id=str(pref.id), attribute=pref.attribute)
    elif action == "restore":
        pref.archived = False
        logger.info("preference_restored", id=str(pref.id), attribute=pref.attribute)
    else:
        raise ValidationError(
            f"acao invalida: {action!r} (use 'edit'|'remove'|'restore')"
        )

    await db_session.commit()
    await db_session.refresh(pref)
    return pref


def _coerce_uuid(raw: str):
    """Aceita UUID em string ou objeto UUID; falha cedo com ValueError claro."""
    from uuid import UUID

    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"preference_id invalido: {raw!r}") from exc


def _sqlite_path_from_url(database_url: str) -> Path | None:
    """Extrai o caminho do arquivo SQLite de uma URL SQLAlchemy.

    Ex.: ``sqlite+aiosqlite:///./data/agentflow.db`` -> ``./data/agentflow.db``.
    Retorna ``None`` se a URL não for SQLite baseada em arquivo (ex.: memória).
    """
    if "sqlite" not in database_url or ":///" not in database_url:
        return None
    raw = database_url.split(":///", 1)[1]
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    if not raw or raw == ":memory:":
        return None
    return Path(raw)


def get_preferences_for_card(card: Any) -> list[str]:
    """Recupera as preferências ativas do usuário dono do projeto do card.

    Débito da Fase D1 resolvido: ``inject_context`` (Fase B2) é **síncrona** e
    roda sob o event loop ativo do FastAPI, então não pode abrir uma sessão
    SQLAlchemy async concorrente. Usa uma conexão ``sqlite3`` síncrona,
    somente-leitura, temporária contra o arquivo do banco local.

    Filtra preferências ``archived = 0`` e ``confidence_count >= 2``
    (limiar de aplicação, evita overfitting em 1 evento — F-010). Formata cada
    preferência como ``"<attribute>: <value>"``.

    Fail-open: retorna lista vazia se o banco/usuário/projeto não existir ou em
    qualquer erro de leitura — nunca levanta (uso em ``inject_context``).
    """
    project_id = _project_id_for_card(card)
    if not project_id:
        return []

    db_path = _sqlite_path_from_url(get_settings().database_url)
    if db_path is None or not db_path.exists():
        logger.debug("get_preferences_no_db", path=str(db_path))
        return []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        logger.debug("get_preferences_connect_failed", error=str(exc))
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM projects WHERE id = ?",
            (_hex_id(project_id),),
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return []
        user_id = row[0]

        cur.execute(
            """
            SELECT attribute, value
            FROM user_preferences
            WHERE user_id = ?
              AND archived = 0
              AND confidence_count >= ?
            ORDER BY last_reinforced_at DESC
            """,
            (user_id, APPLY_THRESHOLD),
        )
        prefs = [f"{attr}: {value}" for attr, value in cur.fetchall()]
        return prefs
    except sqlite3.Error as exc:
        logger.debug("get_preferences_query_failed", error=str(exc))
        return []
    finally:
        conn.close()


def _project_id_for_card(card: Any) -> Any | None:
    """Extrai o project_id do card (atributo direto ou via meta)."""
    project_id = getattr(card, "project_id", None)
    if project_id:
        return project_id
    meta = getattr(card, "meta", None)
    if isinstance(meta, dict):
        return meta.get("project_id")
    return None


def _hex_id(value: Any) -> str:
    """Normaliza um UUID (str com/sem hífens ou objeto) para hex de 32 chars.

    O SQLite do projeto armazena UUIDs como hex sem hífens (ver base.uuid_pk).
    """
    from uuid import UUID

    if isinstance(value, UUID):
        return value.hex
    text = str(value).strip()
    try:
        return UUID(text).hex
    except (ValueError, AttributeError, TypeError):
        return text.replace("-", "")
