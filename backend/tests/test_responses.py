"""Testes unitários do envelope de resposta padronizado (api-patterns).

Garante que todo retorno respeita {success, data|error, meta{request_id}}.
"""

import time
from uuid import uuid4

from app.core.responses import (
    error_envelope,
    paginated_envelope,
    success_envelope,
)


def test_success_envelope_shape() -> None:
    request_id = str(uuid4())
    result = success_envelope(data={"id": "abc"}, request_id=request_id)
    assert result["success"] is True
    assert result["data"] == {"id": "abc"}
    assert "error" not in result
    assert result["meta"]["request_id"] == request_id
    assert "timestamp" in result["meta"]


def test_success_envelope_forbids_error_key() -> None:
    result = success_envelope(data={}, request_id="r1")
    assert "error" not in result


def test_error_envelope_shape() -> None:
    request_id = str(uuid4())
    result = error_envelope(
        code="VALIDATION_ERROR",
        message="Campo invalido",
        request_id=request_id,
        details=[{"field": "email", "issue": "formato"}],
    )
    assert result["success"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["message"] == "Campo invalido"
    assert result["error"]["details"][0]["field"] == "email"
    assert "data" not in result
    assert result["meta"]["request_id"] == request_id


def test_error_envelope_without_details_has_none() -> None:
    result = error_envelope(code="NOT_FOUND", message="ausente", request_id="r2")
    assert result["error"]["details"] is None


def test_paginated_envelope_includes_pagination_meta() -> None:
    request_id = str(uuid4())
    result = paginated_envelope(
        data=[{"id": "1"}, {"id": "2"}],
        total=42,
        page=1,
        per_page=2,
        request_id=request_id,
    )
    assert result["success"] is True
    assert result["meta"]["pagination"] == {
        "total": 42,
        "page": 1,
        "per_page": 2,
        "total_pages": 21,
    }


def test_request_id_is_always_present() -> None:
    result = success_envelope(data={}, request_id="x")
    assert result["meta"]["request_id"] == "x"
    assert isinstance(result["meta"]["timestamp"], str)
