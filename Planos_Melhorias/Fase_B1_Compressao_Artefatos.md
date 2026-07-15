# Fase B1 — Compressão de Artefatos entre Agentes

**Tipo de tarefa:** adaptação de compressor de contexto (usa LLM auxiliar barato).
**Modelo sugerido:** Opus ou Sonnet (precisa entender o compressor e integrar com LLM existente).
**Tempo estimado:** ~8h.

---

## 1. Objetivo

O relatório do SRA (Markdown de 8 seções) e o output do Code Research podem ser
grandes e encarecer o contexto dos agentes seguintes. Comprimir antes de passar
ao Planner/Reviewer.

## 2. Origem no Hermes (copiar lógica, remover imports)

- `Hermes\hermes-agent\agent\context_compressor.py` → classe auto-contida de
  compressão (protege head/tail, template estruturado Resolved/Pending, orçamento
  de resumo proporcional ao conteúdo).
- `Hermes\hermes-agent\agent\conversation_compression.py::prune_tool_output` →
  pré-passe barato que corta saída de ferramenta antes do LLM resumir.

**Obrigatório:** o compressor original usa `agent.auxiliary_client.call_llm`.
Substituir por `backend/app/services/llm.py` (modelo auxiliar barato, configurável
via `app/core/config.py`). Remover `hermes_*`.

## 3. O que criar (sem nome hermes)

### 3.1 `backend/app/services/artifact_compressor.py`
```python
"""Compressão de artefatos entre agentes (adaptado de Hermes context_compressor)."""
from app.services.llm import call_aux_llm  # modelo barato

COMPRESS_THRESHOLD_CHARS = 4000

def prune_tool_output(text: str) -> str:
    """Pré-passe barato: corta saída verbose antes do LLM resumir."""

def compress_artifact(text: str, budget_tokens: int = 800) -> str:
    """Resume relatórios grandes (ex: SRA) preservando seções-chave."""
```

Regras:
- Só comprime se `len(text) > COMPRESS_THRESHOLD_CHARS`.
- Preserva as seções "concorrentes" e "gaps" do relatório SRA.
- Usa `call_aux_llm` (não o modelo principal) para custo baixo.

### 3.2 Integração em `backend/app/services/orchestrator.py` (ou no serviço que
transita `researching→planning`)
Ao mover o Artifact do SRA para o Planner, chama `compress_artifact` se grande.

### 3.3 Respeitar `BudgetLimit` (F-011) — não estourar o cap de custo com compressão.

## 4. Critérios de Aceitação (testáveis)
- [ ] Relatório SRA de exemplo (≥8k chars) comprimido para ≤30% do original sem
      perder "concorrentes" e "gaps".
- [ ] Nenhum import `hermes_*` ou `agent.` no módulo.
- [ ] `pytest` com fixture de relatório grande (mock do `call_aux_llm`).

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
python -c "from app.services.artifact_compressor import compress_artifact; print(len(compress_artifact('x'*9000)))"
```

## 6. Arquivos a ler antes de codar
- `backend/app/services/llm.py` (como chamar modelo auxiliar)
- `backend/app/core/config.py` (modelo auxiliar, orçamento)
- `Cria\PRD_AgentFlow_Studio_v1_1.md` §2.3 (relatório SRA de 8 seções)
- `Hermes\hermes-agent\agent\context_compressor.py`, `conversation_compression.py`
