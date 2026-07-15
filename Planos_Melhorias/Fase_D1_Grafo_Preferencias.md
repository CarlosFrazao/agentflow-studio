# Fase D1 — Grafo de Preferências Aprendidas (F-010)

**Tipo de tarefa:** construir grafo de preferências + mutação arquivável.
**Modelo sugerido:** Haiku ou Sonnet (lógica de grafo, baixo/médio esforço).
**Tempo estimado:** ~9h.
**Compartilha:** tabela `user_preferences` (já existe em `app/models/user_preference.py`) com a Fase D2.

---

## 1. Objetivo

O F-010 guarda preferências em `user_preferences` (confiança ≥2), mas não as
relaciona nem as visualiza. Construir um grafo "aprendizado visível" e permitir
editar/remover (arquivar recuperável).

## 2. Origem no Hermes (copiar lógica, remover imports)

- `Hermes\hermes-agent\agent\learning_graph.py` → monta grafo: nós = skills
  aprendidas + memórias; arestas de `related_skills` e sobreposição lexical.
- `Hermes\hermes-agent\agent\learning_mutations.py` → `parse_node_kind`,
  mutação de nós (deletar = arquivar recuperável; editar = reescrever arquivo).

**Obrigatório:** o hermes usa `MEMORY.md`/`USER.md`/`get_hermes_home`. Substituir
por leitura da tabela `user_preferences` do AgentFlow. Remover `hermes_*`.

## 3. O que criar (sem nome hermes)

### 3.1 `backend/app/services/preference_graph.py`
```python
"""Grafo de preferências aprendidas (adaptado de Hermes learning_graph)."""
from app.models.user_preference import UserPreference

def build_graph(db_session) -> dict:
    """Nós = UserPreference ativas; arestas = co-ocorrência + sobreposição lexical."""

def mutate_preference(db_session, user_id, attr: str, action: str) -> None:
    """edit | remove. remove = arquivar (recuperável), não apaga histórico."""
```

### 3.2 Integração com UI (PRD F-010 / UI §5)
`build_graph` exporta JSON para o frontend desenhar o grafo na tela
"Preferências Aprendidas". (O frontend consome via endpoint — criar se não houver.)

### 3.3 `mutate_preference(action="remove")` arquiva (flag `archived=True` na tabela
ou tabela `user_preference_archive`), permitindo restore.

## 4. Critérios de Aceitação (testáveis)
- [ ] Grafo gerado a partir de `user_preferences` reais (nós + arestas).
- [ ] Remoção de preferência arquiva (recuperável) e não apaga histórico.
- [ ] `pytest` cobre `build_graph` e `mutate_preference`.
- [ ] Sem nome hermes.

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
python -c "from app.services.preference_graph import build_graph; print(build_graph(next(get_db())))"
```

## 6. Arquivos a ler antes de codar
- `backend/app/models/user_preference.py` (schema existente)
- `Cria\PRD_AgentFlow_Studio_v1_1.md` §2.10 (F-010) e UI §5
- `Hermes\hermes-agent\agent\learning_graph.py`, `learning_mutations.py`
