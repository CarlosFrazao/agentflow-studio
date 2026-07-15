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


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


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
