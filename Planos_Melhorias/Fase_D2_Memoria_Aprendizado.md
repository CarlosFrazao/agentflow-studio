# Fase D2 — Memória de Aprendizado Incremental

**Tipo de tarefa:** camada de memória leve que grava/recupera lições entre execuções.
**Modelo sugerido:** Haiku ou Sonnet.
**Tempo estimado:** ~8h.
**Usado por:** Fase B2 (`inject_context` consome `recall_lessons`).

---

## 1. Objetivo

Lições de execuções passadas (ex: "Firecrawl caiu na porta 3022", "SRA demora >
90s em modo cirurgia") não são persistidas. Criar camada que grava lições e as
injeta no prompt do agente correspondente.

## 2. Origem no Hermes (copiar lógica, remover imports)

- `Hermes\hermes-agent\agent\memory_manager.py` + `memory_provider.py` → camada de
  memória (append/recupera chunks, provedor pluggável).
- `Hermes\hermes-agent\agent\learning_mutations.py` → mutação de memórias.

**Obrigatório:** o hermes usa `MEMORY.md`/`USER.md`. Usar
`data/agent_lessons.md` local do AgentFlow (ou tabela `agent_lessons` via nova
migration Alembic). Remover `hermes_*`.

## 3. O que criar (sem nome hermes)

### 3.1 `backend/app/services/learning_memory.py`
```python
"""Memória de aprendizado incremental (adaptado de Hermes memory_manager)."""
from pathlib import Path

LESSONS_PATH = Path(__file__).resolve().parents[2] / "data" / "agent_lessons.md"

class LearningMemory:
    def record_lesson(self, agent: str, lesson: str) -> None: ...
    def recall_lessons(self, agent: str, k: int = 5) -> list[str]: ...

# TODO (modelo executor): persistir em data/agent_lessons.md (formato markdown)
# ou em tabela agent_lessons (escolher um; se tabela, criar migration Alembic).
```

### 3.2 Injeção no prompt (usado pela Fase B2)
O orchestrator chama `recall_lessons(agent)` e concatena ao prompt do agente. Se o
arquivo/módulo não existir, `inject_context` (B2) faz fallback silencioso.

## 4. Critérios de Aceitação (testáveis)
- [ ] Lição gravada é recuperada e pode ser injetada no prompt do agente.
- [ ] `pytest` com round-trip record/recall (fixture de arquivo temporário).
- [ ] Sem nome hermes.

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
python -c "from app.services.learning_memory import LearningMemory; m=LearningMemory(); m.record_lesson('research','Firecrawl caiu na 3022'); print(m.recall_lessons('research'))"
```

## 6. Arquivos a ler antes de codar
- `backend/app/services/prompt_hydration.py` (onde injetar contexto)
- `backend/data/` (verificar se existe; criar se necessário)
- `Cria\Spec_Tecnica_Integracao_v1_0.md` §1.3/§2.3 (lições reais: porta 3022 vs 3002)
- `Hermes\hermes-agent\agent\memory_manager.py`, `memory_provider.py`
