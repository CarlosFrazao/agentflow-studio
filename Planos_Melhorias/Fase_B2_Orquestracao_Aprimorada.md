# Fase B2 — Orquestração Aprimorada (retomável + lições)

**Tipo de tarefa:** estender a máquina de estados do orchestrator para retomada e injeção de contexto.
**Modelo sugerido:** Sonnet.
**Tempo estimado:** ~7h.
**Depende de:** Fase B1 (opcional — usa `artifact_compressor` se existir) e Fase D2 (learning_memory).

---

## 1. Objetivo

`backend/app/services/orchestrator.py` hoje é puro (máquina de estados). Adicionar:
- Retomada de card após restart do backend (reposiciona no agente correto).
- Log estruturado do ciclo Criação↔Revisão (Item B do PRD).
- Injeção de lições aprendidas (`learning_memory`) e preferências (`preference_graph`)
  no prompt dos agentes.

## 2. Origem no Hermes (copiar helpers aplicáveis, renomear)

- `Hermes\hermes-agent\agent\agent_runtime_helpers.py` → helpers de runtime/
  depuração de agentes (pause/resume, inspeção de estado). **Não copiar o
  arquivo inteiro** (é enorme) — só as funções de resume/inspeção aplicáveis,
  renomeadas para o namespace do AgentFlow.

**Obrigatório:** remover `hermes_*`, `agent.` dos imports.

## 3. O que criar/estender (sem nome hermes)

### 3.1 Estender `backend/app/services/orchestrator.py`
```python
def resume_from_column(column: str) -> str | None:
    """Recalcula o agente correto ao retomar um card (após restart)."""

def handle_review_cycle(card, review_passed: bool, confidence: float, critical_alerts: int) -> str:
    """Wrapper sobre column_after_review com logging estruturado do ciclo."""

def inject_context(card, base_prompt: str) -> str:
    """Injeta lições (learning_memory) + preferências (preference_graph) no prompt.
    Fallback silencioso se os módulos não existirem ainda."""
```
- `resume_from_column` reaproveita `COLUMN_TO_AGENT` (já existe).
- `handle_review_cycle` chama `column_after_review` (já existe) e faz `logger.info`.

### 3.2 `inject_context` (nova)
Lê lições de `app/services/learning_memory.py` (Fase D2) e preferências de
`app/services/preference_graph.py` (Fase D1); concatena ao prompt só se houver
conteúdo. Usar `try/except ImportError` para não acoplar a ordem das fases.

## 4. Critérios de Aceitação (testáveis)
- [ ] `resume_from_column("researching")` retorna `"research"`.
- [ ] Ciclo de revisão reprovado logado e retorna `"production"` (ver `column_after_review`).
- [ ] `pytest` cobre `resume_from_column` e `handle_review_cycle`.
- [ ] Sem nome hermes em nenhum arquivo novo.

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
python -c "from app.services.orchestrator import resume_from_column; print(resume_from_column('planning'))"
```

## 6. Arquivos a ler antes de codar
- `backend/app/services/orchestrator.py` (atual — já lido, tem COLUMN_TO_AGENT, column_after_review)
- `backend/app/services/learning_memory.py` (Fase D2, opcional)
- `backend/app/services/preference_graph.py` (Fase D1, opcional)
- `Cria\PRD_AgentFlow_Studio_v1_1.md` §2.6 (ciclo Criação↔Revisão)
- `Hermes\hermes-agent\agent\agent_runtime_helpers.py` (só funções de resume/inspeção)
