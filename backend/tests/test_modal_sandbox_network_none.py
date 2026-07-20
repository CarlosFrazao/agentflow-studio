"""TDD: Modal sandbox isolates network (B7-2).

The `modal` SDK is optional (graceful degradation), so we inject a fake
`modal` module into sys.modules and assert that `@app.function` receives
`network_access=False` -- the Modal equivalent of docker's `--network none`.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.sandbox.base import SandboxResult


class _CapturingApp:
    """Fake modal.App that records @function kwargs."""

    _instance: "_CapturingApp" | None = None

    def __init__(self) -> None:
        self.function_kwargs: dict = {}

    @staticmethod
    def lookup(*_a, **_k) -> "_CapturingApp":
        assert _CapturingApp._instance is not None
        return _CapturingApp._instance

    def function(self, **kwargs):
        self.function_kwargs.update(kwargs)

        def decorator(fn):
            # Modal's `@function` returns the decorated callable; the code
            # calls `_run.remote.aio(code)`, so the returned object must expose
            # `.remote.aio(...)` that awaits `fn`.
            return _Function(fn)

        return decorator


class _Function:
    """Wraps the decorated coroutine so `_run.remote.aio(code)` runs it."""

    def __init__(self, fn) -> None:
        self._fn = fn
        self.remote = self

    async def aio(self, *a, **k):
        return await self._fn(*a, **k)


class _Image:
    def pip_install(self, *a, **k):
        return self


def _make_fake_modal() -> tuple[types.ModuleType, _CapturingApp]:
    fake = types.ModuleType("modal")

    def debian_slim() -> _Image:
        return _Image()

    fake.Image = type("Image", (), {"debian_slim": staticmethod(debian_slim)})
    instance = _CapturingApp()
    _CapturingApp._instance = instance
    fake.App = _CapturingApp
    return fake, instance


class _FakeCompleted:
    """Stand-in for subprocess.CompletedProcess."""

    returncode = 0
    stderr = ""


@pytest.fixture
def fake_modal(monkeypatch):
    fake, app_instance = _make_fake_modal()
    monkeypatch.setitem(sys.modules, "modal", fake)
    # The real `_run` spawns `python <tmp>.py` inside the OS; we only care
    # that `@app.function` is declared with network isolation, so stub the
    # subprocess call to keep the test deterministic across platforms.
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeCompleted())
    from app.sandbox.modal_sandbox import ModalSandbox

    return ModalSandbox(), app_instance


@pytest.mark.asyncio
async def test_modal_function_declares_network_none(fake_modal) -> None:
    sandbox, app_instance = fake_modal
    result = await sandbox.validate("print(1)")
    assert isinstance(result, SandboxResult)
    assert app_instance.function_kwargs.get("network_access") is False
    assert result.backend == "modal"
    assert result.success is True
