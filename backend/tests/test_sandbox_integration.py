"""Testes de integração dos backends de sandbox reais (Item E).

Cobre: DockerSandbox via subprocess mockado, e branches de degradação
graciosa do AWSLambda/Modal quando as libs não estão instaladas.
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.sandbox.aws_sandbox import AWSLambdaSandbox
from app.sandbox.docker_sandbox import DockerSandbox
from app.sandbox.modal_sandbox import ModalSandbox
from app.sandbox.base import SandboxResult

pytestmark = pytest.mark.asyncio


async def test_docker_sandbox_success(monkeypatch) -> None:
    class FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"", b"")

    async def fake_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = DockerSandbox()
    result = await backend.validate("print(1)")
    assert result.success is True
    assert result.backend == "docker"


async def test_docker_sandbox_failure(monkeypatch) -> None:
    class FakeProc:
        returncode = 1

        async def communicate(self):
            return (b"", b"erro de sintaxe")

    async def fake_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = DockerSandbox()
    result = await backend.validate("x =")
    assert result.success is False
    assert "erro" in result.stderr


async def test_docker_sandbox_no_binary(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", boom)
    backend = DockerSandbox()
    result = await backend.validate("print(1)")
    assert result.success is False
    assert "docker executable" in result.stderr


async def test_aws_sandbox_without_boto3(monkeypatch) -> None:
    # simula import ausente
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "boto3":
            raise ImportError("no boto3")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = AWSLambdaSandbox()
    result = await backend.validate("print(1)")
    assert result.success is False
    assert "boto3" in result.stderr


async def test_modal_sandbox_without_sdk(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "modal":
            raise ImportError("no modal")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = ModalSandbox()
    result = await backend.validate("print(1)")
    assert result.success is False
    assert "modal" in result.stderr
