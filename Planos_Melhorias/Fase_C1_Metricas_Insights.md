# Fase C1 — Motor de Métricas para Dashboard (F-013)

**Tipo de tarefa:** adaptar motor de insights de uso/custo para o SQLite do AgentFlow.
**Modelo sugerido:** Sonnet.
**Tempo estimado:** ~10h.

---

## 1. Objetivo

O Dashboard simplificado (F-013) precisa de custo por projeto/agente, padrões de
uso e taxa de auto-approve. Reutilizar o motor de insights do Hermes, lendo do
SQLite do AgentFlow.

## 2. Origem no Hermes (copiar lógica, remover imports)

- `Hermes\hermes-agent\agent\insights.py` → `InsightsEngine.generate(days)`,
  `format_terminal`; analisa SQLite para tokens, custo, ferramentas, tendências,
  breakdown por modelo. **Adaptar para ler do schema do AgentFlow**, não do
  `hermes_state`.
- `Hermes\hermes-agent\agent\usage_pricing.py` → `estimate_usage_cost`,
  `CanonicalUsage`, `format_duration_compact` (estimativa de custo).

**Obrigatório:** trocar a fonte SQLite (`hermes_state`) pelas tabelas do AgentFlow
(`app/models/execution.py`, `app/models/budget.py`). Remover `hermes_*`.

## 3. O que criar (sem nome hermes)

### 3.1 `backend/app/services/metrics_insights.py`
```python
"""Motor de insights de uso/custo (adaptado de Hermes insights.py)."""
from app.models.execution import Execution
from app.models.budget import BudgetLimit
from app.services.orchestrator import should_auto_approve

class InsightsEngine:
    def __init__(self, db_session): ...
    def generate(self, days: int = 30) -> "MetricsReport": ...
    def format_dashboard(self, report) -> dict: ...

@dataclass
class MetricsReport:
    total_cost_usd: float
    cost_by_project: dict
    cost_by_agent: dict
    avg_time_per_phase: dict
    auto_approve_rate: float
    reversal_rate: float
    spend_vs_limit: dict   # respeita BudgetLimit (F-011)
```
- `auto_approve_rate` usa `should_auto_approve` (já existe no orchestrator).
- `spend_vs_limit` lê `BudgetLimit.current_month_spend_usd` vs limites.

### 3.2 Endpoint `GET /api/metrics/insights?days=30`
Em `backend/app/api/` (seguir padrão dos routers existentes em `app/api/`).
Retorna `format_dashboard(report)` como JSON.

### 3.3 Respeitar `BudgetLimit` (F-011): incluir "gasto vs limite" no payload.

## 4. Critérios de Aceitação (testáveis)
- [ ] Relatório inclui custo por projeto e por agente derivado das Executions.
- [ ] Taxa de auto-approve calculada e exposta.
- [ ] Endpoint retorna JSON válido; `pytest` com banco seedado (conftest existente).
- [ ] Sem dependência de `hermes_*`/`agent.`.

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
# subir backend e curl GET /api/metrics/insights?days=30  -> JSON com cost_by_project
```

## 6. Arquivos a ler antes de codar
- `backend/app/models/execution.py`, `backend/app/models/budget.py`
- `backend/app/api/` (padrão de routers; ex: `app/api/deps.py`)
- `backend/app/services/orchestrator.py` (`should_auto_approve`)
- `Cria\PRD_AgentFlow_Studio_v1_1.md` §2.13 (Dashboard F-013)
- `Hermes\hermes-agent\agent\insights.py`, `usage_pricing.py`
