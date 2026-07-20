"""Envelope de resposta padronizado (skill api-patterns).

Todo retorno da API segue:
  { success, data | error, meta{ request_id, timestamp, pagination? } }

Regras inegociáveis:
- `success` sempre presente.
- `data` presente apenas em sucesso.
- `error.code` em SCREAMING_SNAKE_CASE.
- `meta.request_id` sempre presente (rastreabilidade).
- Nunca expor stack trace / SQL.
"""

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import AppError


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def sanitize_error(exc: Exception) -> str:
    """Converte detalhes de erro internos em mensagem segura para o envelope.

    - AppError (erros de domínio esperados): expõe a própria mensagem — segura
      por design e útil para o cliente distinguir falhas conhecidas.
    - Exceções genéricas (RuntimeError, KeyError, ...): NÃO vazam o str(exc) cru
      (que pode conter stack/privados/paths); retornam mensagem genérica. O
      detalhe real fica no log do servidor (logger.error).
    """
    if isinstance(exc, AppError):
        return exc.message
    return "Erro interno. Consulte o request_id para rastreabilidade."


def success_envelope(data: Any, request_id: str) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "meta": {
            "request_id": request_id,
            "timestamp": _now_iso(),
        },
    }


def paginated_envelope(
    data: list[Any],
    total: int,
    page: int,
    per_page: int,
    request_id: str,
) -> dict[str, Any]:
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    return {
        "success": True,
        "data": data,
        "meta": {
            "request_id": request_id,
            "timestamp": _now_iso(),
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            },
        },
    }


def error_envelope(
    code: str,
    message: str,
    request_id: str,
    details: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "meta": {
            "request_id": request_id,
            "timestamp": _now_iso(),
        },
    }
