# Imagem de sandbox do Dev Agent (F-006 / Spec §3.2).
#
# O backend (app/sandbox/docker_sandbox.py) roda o código gerado com:
#   docker run --rm --network none -e DISABLED \
#     -v <tmp>:/sandbox/code.py:ro agentflow-sandbox:latest \
#     python /sandbox/code.py
#
# Portanto esta imagem só precisa de `python` no PATH. O container é sempre
# lançado com --network none (sem rede) e a env var DISABLED (sinaliza que
# não há env vars do host disponíveis). Nada de ENTRYPOINT customizado:
# o comando `python /sandbox/code.py` já é passado pelo docker_sandbox.

FROM python:3.12-slim

# Sem rede em runtime; instalamos apenas o essencial para validar a execução
# de código Python puro gerado pelos agents. Pip fica disponível caso o
# Dev Agent precise validar trechos que importem libs da stdlib estendida.
WORKDIR /sandbox

# Usuário não-root para reduzir a superfície de ataque dentro do container.
RUN useradd --create-home --uid 10001 sandboxer
USER sandboxer

# O código é montado em /sandbox/code.py em runtime (read-only). Nada a copiar
# na imagem.
CMD ["python", "/sandbox/code.py"]
