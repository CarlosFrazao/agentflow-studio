"""Constrói a imagem Docker do sandbox do Dev Agent (agentflow-sandbox:latest).

O DockerSandbox (app/sandbox/docker_sandbox.py) executa o código gerado em
`docker run --rm --network none agentflow-sandbox:latest python /sandbox/code.py`.
Esta imagem é construída por este script (não pelo docker-compose do app).

Uso:
    python scripts/build_sandbox_image.py            # build padrão
    AGentflow_SANDBOX_TAG=my-tag python scripts/build_sandbox_image.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SANDBOX_DIR = Path(__file__).resolve().parent.parent / "sandbox"
TAG = os.environ.get("AGENTFLOW_SANDBOX_TAG", "agentflow-sandbox:latest")


def main() -> int:
    if not SANDBOX_DIR.joinpath("Dockerfile").exists():
        print(f"ERRO: Dockerfile ausente em {SANDBOX_DIR}", file=sys.stderr)
        return 1
    print(f"Construindo imagem '{TAG}' a partir de {SANDBOX_DIR} ...")
    try:
        proc = subprocess.run(
            ["docker", "build", "-t", TAG, str(SANDBOX_DIR)],
            check=False,
        )
    except FileNotFoundError:
        print(
            "ERRO: 'docker' não encontrado no PATH. Instale o Docker ou use um "
            "sandbox fake nos testes (override de get_sandbox).",
            file=sys.stderr,
        )
        return 2
    if proc.returncode != 0:
        print(f"ERRO: build da imagem falhou (rc={proc.returncode}).", file=sys.stderr)
        return proc.returncode
    print(f"OK: imagem '{TAG}' construída.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
