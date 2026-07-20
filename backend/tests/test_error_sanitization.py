"""FEAT-006 (T6): sanitização de erro no envelope (B6-2/B5-5).

Garante que erros internos (exceções genéricas) NÃO vazam o str(exc) cru no
envelope HTTP nem no stderr dos sandboxes de infra; AppErrors conhecidos
continuam expostos (safe by design); o request_id é preservado para
rastreabilidade e o detalhe real fica no log do servidor.
"""

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import sanitize_error


def test_generic_exception_is_sanitized() -> None:
    exc = RuntimeError("traceback com /abs/path e 'secret_key'")
    msg = sanitize_error(exc)
    assert "/abs/path" not in msg
    assert "secret_key" not in msg
    assert msg == "Erro interno. Consulte o request_id para rastreabilidade."


def test_app_error_preserves_safe_message() -> None:
    exc = ValidationError("email em formato invalido")
    assert sanitize_error(exc) == "email em formato invalido"


def test_app_error_subclass_preserves_safe_message() -> None:
    exc = NotFoundError("Card", "abc-123")
    assert sanitize_error(exc) == "Card not found: abc-123"


@pytest.mark.asyncio
async def test_aws_sandbox_does_not_leak_raw_error(monkeypatch) -> None:
    import builtins

    from app.sandbox.aws_sandbox import AWSLambdaSandbox

    class _BoomClient:
        def invoke(self, **kwargs):
            raise RuntimeError("/root/.aws/credentials: permission denied")

    class _BoomBoto3:
        def client(self, name):
            return _BoomClient()

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "boto3":
            return _BoomBoto3()
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    backend = AWSLambdaSandbox()
    result = await backend.validate("print(1)")
    assert result.success is False
    assert "/root/.aws/credentials" not in result.stderr
    assert result.stderr == "Erro interno. Consulte o request_id para rastreabilidade."


@pytest.mark.asyncio
async def test_modal_sandbox_does_not_leak_raw_error(monkeypatch) -> None:
    import builtins

    from app.sandbox.modal_sandbox import ModalSandbox

    class _BoomModal:
        def Image(self):
            raise RuntimeError("internal modal /var/run/secret failure")

        def App(self):
            raise RuntimeError("internal modal /var/run/secret failure")

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "modal":
            return _BoomModal()
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    backend = ModalSandbox()
    result = await backend.validate("print(1)")
    assert result.success is False
    assert "/var/run/secret" not in result.stderr
    assert result.stderr == "Erro interno. Consulte o request_id para rastreabilidade."
