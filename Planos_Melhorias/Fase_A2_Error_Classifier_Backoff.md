# Fase A2 — Classificação de Erros + Backoff (Resiliência)

**Tipo de tarefa:** adaptação mecânica de módulos de retry/failover para os clients existentes.
**Modelo sugerido:** Haiku (tarefa mecânica de copy-adapt, baixo raciocínio).
**Tempo estimado:** ~10h.

---

## 1. Objetivo

Dar aos clients SRA/Firecrawl/GitHub (PRD F-003/F-008, Spec §5) classificação
fina de erros para decidir a ação de recuperação, e backoff com jitter para
evitar rajadas de retry (thundering herd).

## 2. Origem no Hermes (copiar lógica, remover imports)

- `Hermes\hermes-agent\agent\error_classifier.py` → enum `FailoverReason`
  (auth, auth_permanent, billing, rate_limit, upstream_rate_limit, overloaded,
  server_error, timeout, tls…) e pipeline de classificação que recebe uma
  exceção e devolve o `FailoverReason` + ação sugerida.
- `Hermes\hermes-agent\agent\retry_utils.py` → `adaptive_rate_limit_backoff`,
  backoff descorrelacionado com jitter (`_jitter_counter`, `_jitter_lock`).

**Obrigatório:** remover `hermes_*` e `agent.` do import; a taxonomia
`FailoverReason` é stdlib pura (enum/dataclass) — copiar tal qual.

## 3. O que criar (sem nome hermes)

### 3.1 `backend/app/clients/error_classifier.py`
```python
"""Classificação de erros de API para failover/recuperação (adaptado de Hermes)."""
import enum
from dataclasses import dataclass

class FailoverReason(enum.Enum):
    auth = "auth"
    auth_permanent = "auth_permanent"
    billing = "billing"
    rate_limit = "rate_limit"
    overloaded = "overloaded"
    server_error = "server_error"
    timeout = "timeout"
    tls = "tls"

# TODO (modelo executor): classify(exc) -> FailoverReason
# mapeia httpx.HTTPStatusError / httpx.RequestError -> FailoverReason
```

### 3.2 `backend/app/clients/backoff.py`
```python
"""Backoff com jitter (adaptado de Hermes retry_utils)."""
import random, threading, time
# TODO: jittered_backoff(attempt)->float ; adaptive_rate_limit_backoff(attempt)->float
```

### 3.3 Estender `backend/app/clients/circuit_breaker.py` (já existe)
Ao `record_failure`, aceitar um `reason: FailoverReason | None` e registrá-lo
no log de incidente (já previsto na Spec §5). **Não quebrar** a API atual nem os
testes existentes (`backend/tests/...`).

### 3.4 Clients SRA/Firecrawl/GitHub
Chamar `classify()` para escolher: retry com `jittered_backoff`, fallback
(SRA→REST quando MCP cai), ou abortar com aviso "pesquisa incompleta" (Spec §5).

## 4. Critérios de Aceitação (testáveis)
- [ ] 429 → `rate_limit` → `adaptive_rate_limit_backoff`.
- [ ] 503 → `overloaded`; 401 → `auth`; 5xx → `server_error`.
- [ ] 100% dos testes de `circuit_breaker.py` existentes continuam passando.
- [ ] Nenhum arquivo novo contém "hermes".

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
python -c "from app.clients.error_classifier import classify; from app.clients.backoff import jittered_backoff; print(classify.__name__, jittered_backoff(1))"
```

## 6. Arquivos a ler antes de codar
- `backend/app/clients/circuit_breaker.py` (estender, não reescrever)
- `backend/app/clients/sra_client.py` (se existir) ou criar wrapper
- `Cria\Spec_Tecnica_Integracao_v1_0.md` §5 (comportamento de degradação)
- `Hermes\hermes-agent\agent\error_classifier.py`, `retry_utils.py`
