# Plano Completo de Integração de Inteligência de Agentes

**Projeto alvo:** AgentFlow Studio (`F:\Criando sites pelo pc\Site AgentFlow Studio`)
**Fonte de inspiração:** diretório `Hermes\hermes-agent` (capacidades de agentes, sem reuso do nome)
**Data:** 2026-07-13
**Regra rígida:** nenhum arquivo novo do AgentFlow pode conter o nome "hermes" — toda capacidade é renomeada e adaptada.

---

## 0. Princípio de Reutilização

O `hermes-agent` já implementa, de forma madura, várias capacidades que o
AgentFlow Studio precisa mas ainda não tem (ou tem de forma incipiente). Em vez
de reimplementar do zero, **copiamos a lógica relevante, removemos os imports
específicos do hermes** (`hermes_constants`, `agent.*`, `hermes_state`,
`get_hermes_home`, etc.) **e a encaixamos nas pastas já existentes do backend**
(`app/services`, `app/clients`, `app/core`). Onde o AgentFlow já tem código
equivalente (ex: `circuit_breaker.py`, `orchestrator.py`), **estendemos** em vez
de duplicar.

Capacidades mapeadas (origem → destino no AgentFlow):

| Capacidade no hermes-agent | Onde vive no hermes | Destino no AgentFlow |
|---|---|---|
| Geração/empacotamento de skills | `agent/skill_bundles.py`, `agent/skill_preprocessing.py`, `agent/skill_utils.py` | `backend/app/services/skill_factory.py` + `.claude/skills/auto-skill-generator/` |
| Compressão de contexto/artefatos | `agent/context_compressor.py`, `agent/conversation_compression.py` | `backend/app/services/artifact_compressor.py` |
| Classificação de erros e failover | `agent/error_classifier.py` | `backend/app/clients/error_classifier.py` |
| Retry com jitter (backoff descorrelacionado) | `agent/retry_utils.py` | `backend/app/clients/backoff.py` (estende `app/clients/retry.py`) |
| Insights de uso/custo | `agent/insights.py`, `agent/usage_pricing.py` | `backend/app/services/metrics_insights.py` (alimenta F-013) |
| Grafo de aprendizado (skills+memória) | `agent/learning_graph.py`, `agent/learning_mutations.py` | `backend/app/services/preference_graph.py` (alimenta F-010) |
| Gerenciamento de memória/aprendizado incremental | `agent/memory_manager.py`, `agent/memory_provider.py` | `backend/app/services/learning_memory.py` |
| Ajuda de runtime/orquestração de agentes | `agent/agent_runtime_helpers.py` | estende `backend/app/services/orchestrator.py` |

---

## 1. Gerador de Habilidades Dinâmicas (Skill Factory)

**Problema:** hoje as skills do AgentFlow são estáticas. Queremos que, a partir do
PRD v1.1 e da Spec de Integração, o sistema **gere skills customizadas**
automaticamente (ex: `firecrawl-debugger`, `sra-cirurgia-mode`,
`auto-approve-validator`, `github-license-checker`).

**O que reutilizar do hermes:**
- `skill_utils.py::parse_frontmatter`, `SKILL_SUPPORT_DIRS`, `is_excluded_skill_path` → validação de frontmatter YAML das skills geradas.
- `skill_bundles.py` → lógica de empacotar uma skill (SKILL.md + references + templates) num pacote coerente.
- `skill_preprocessing.py` → normalização de nomes/descrições (lowercase, hífens, ≤64 chars, description ≤1024).

**O que criar (sem nome hermes):**
- `backend/app/services/skill_factory.py`
  - `analyze_requirements(prd_path, spec_path) -> list[SkillSpec]` — varre os dois
    docs e extrai "necessidades" (integrações, modos, checagens de licença,
    circuit breakers) via regex/keyword + LLM leve opcional.
  - `generate_skill(spec: SkillSpec) -> Path` — monta um pacote de skill em
    `.claude/skills/auto-skill-generator/<nome>/SKILL.md` usando os templates do
    hermes, com frontmatter validado por `skill_utils.parse_frontmatter`.
  - `SkillSpec` dataclass: `name, description, triggers, body_template, references`.
- `backend/app/services/skill_factory_templates.py` — templates reais de corpo para
  cada skill (firecrawl-debugger usa o endpoint `/v2/scrape` da Spec; sra-cirurgia
  documenta o `--mode cirurgia`; auto-approve-validator repete a regra do ADR-007).
- `.claude/skills/auto-skill-generator/SKILL.md` — a própria skill "meta" que
  instrui o Claude a (re)gerar skills quando o PRD/Spec mudar.

**Critérios de aceitação:**
- [ ] Rodar `skill_factory.analyze_requirements()` sobre PRD+Spec produz ≥4 SkillSpecs.
- [ ] Cada skill gerada passa `parse_frontmatter` (sem erro de YAML).
- [ ] Nenhuma skill gerada contém a palavra "hermes" em nome, corpo ou metadados.
- [ ] `pytest` cobre `analyze_requirements` e `generate_skill` (mock dos docs).

**Esforço:** ~14h (4h análise + 6h templates + 4h testes/validação).

---

## 2. Compressão de Artefatos entre Agentes

**Problema:** o relatório do SRA (Markdown de 8 seções) e o output do Code Research
podem ser grandes e encarecer o contexto dos agentes seguintes (Planner/Reviewer).

**O que reutilizar do hermes:**
- `context_compressor.py` — classe auto-contida de compressão (protege head/tail,
  template estruturado Resolved/Pending, orçamento de resumo proporcional).
- `conversation_compression.py::compress_context` — padrão de dividir a sessão e
  rotacionar id após comprimir.

**O que criar (sem nome hermes):**
- `backend/app/services/artifact_compressor.py`
  - `compress_artifact(text: str, budget_tokens: int) -> str` — usa um modelo
    auxiliar barato (já temos `app/services/llm.py`) para resumir relatórios SRA
    antes de passar ao Planner.
  - `prune_tool_output(text: str) -> str` — pré-passe barato que corta saída de
    ferramenta antes do LLM resumir (do hermes).
  - Integração: no `orchestrator.py`, ao transitar `researching→planning`, comprime
    o Artifact do SRA se `len(text) > COMPRESS_THRESHOLD_CHARS`.
- Respeita `app/core/config.py` (modelo auxiliar configurável via env).

**Critérios de aceitação:**
- [ ] Relatório SRA de exemplo (≥8k chars) é comprimido para ≤30% do original sem
      perder as seções "concorrentes" e "gaps".
- [ ] Nenhum import de `hermes_*` ou `agent.` no módulo.
- [ ] `pytest` com fixture de relatório grande.

**Esforço:** ~8h (4h adaptação + 4h testes).

---

## 3. Resiliência de Integrações (Error Classifier + Backoff)

**Problema:** os clients SRA/Firecrawl/GitHub (PRD F-003/F-008, Spec §5) hoje têm
circuit breaker, mas o tratamento de erro é genérico (timeout/HTTPStatusError).
Queremos classificação fina de erros para decidir a ação de recuperação.

**O que reutilizar do hermes:**
- `error_classifier.py` — taxonomia `FailoverReason` (auth, billing, rate_limit,
  overloaded, server_error, timeout, tls…) e pipeline de classificação
  priorizado que retorna a ação (retry / rotate / fallback / compress / abort).
- `retry_utils.py` — `adaptive_rate_limit_backoff`, backoff descorrelacionado com
  jitter (evita thundering herd).

**O que criar (sem nome hermes):**
- `backend/app/clients/error_classifier.py` — copia a taxonomia e o classificador,
  removendo `hermes_*`; recebe `httpx.HTTPStatusError`/`RequestError` e devolve
  `FailoverReason`.
- `backend/app/clients/backoff.py` — `jittered_backoff(attempt) -> float` e
  `adaptive_rate_limit_backoff(attempt) -> float` (do hermes), usados por
  `app/clients/retry.py`.
- Estender `app/clients/circuit_breaker.py` para, ao abrir, registrar o
  `FailoverReason` no log de incidente (já previsto na Spec §5).
- Clientes SRA/Firecrawl/GitHub chamam o classificador para escolher: retry com
  backoff, fallback (ex: SRA→REST quando MCP cai), ou abortar com aviso "pesquisa
  incompleta" (comportamento da Spec §5).

**Critérios de aceitação:**
- [ ] 429 → `rate_limit` → `adaptive_rate_limit_backoff`.
- [ ] 503 → `overloaded` → backoff; 401 → `auth` (tenta refresh de credencial);
      5xx → `server_error` → retry.
- [ ] 100% dos testes de `circuit_breaker.py` existentes continuam passando.
- [ ] Nenhum nome hermes em arquivos novos.

**Esforço:** ~10h (5h classifier + 3h backoff + 2h testes).

---

## 4. Métricas Avançadas para o Dashboard (F-013)

**Problema:** o Dashboard simplificado (F-013) precisa de custo por projeto/agente,
padrões de uso e taxa de auto-approve — o hermes já tem um motor de insights.

**O que reutilizar do hermes:**
- `insights.py::InsightsEngine` — gera relatório de uso (tokens, custo, ferramentas,
  tendências, breakdown por modelo/plataforma) a partir de um SQLite.
- `usage_pricing.py::estimate_usage_cost`, `CanonicalUsage` — estimativa de custo.

**O que criar (sem nome hermes):**
- `backend/app/services/metrics_insights.py`
  - `InsightsEngine` adaptado para ler do SQLite do AgentFlow (`app/models/execution.py`,
    `app/models/budget.py`).
  - `generate(days=30) -> MetricsReport` — custo total, custo por projeto, custo por
    agente, tempo médio por fase, taxa de auto-approve (usa `orchestrator.should_auto_approve`),
    taxa de reversão.
  - `format_dashboard(report) -> dict` — payload para o frontend (substitui os
    "cards essenciais" do PRD F-013 por dados reais).
- Endpoint novo em `app/api/` (ex: `GET /api/metrics/insights?days=30`) que retorna
  o payload.
- Respeita `BudgetLimit` (F-011): inclui "gasto vs limite" no relatório.

**Critérios de aceitação:**
- [ ] Relatório inclui custo por projeto e por agente derivado das Executions.
- [ ] Taxa de auto-approve calculada e exposta.
- [ ] Endpoint retorna JSON válido; `pytest` com banco seedado.
- [ ] Sem dependência de `hermes_*`/`agent.`.

**Esforço:** ~10h (5h adaptação + 5h endpoint/testes).

---

## 5. Grafo de Preferências Aprendidas (F-010)

**Problema:** o F-010 guarda preferências em `user_preferences` (confiança ≥2), mas
não visualiza nem relaciona preferências entre si nem com skills.

**O que reutilizar do hermes:**
- `learning_graph.py` — monta grafo "aprendizado visível": nós = skills aprendidas +
  memórias; arestas de `related_skills` e sobreposição lexical.
- `learning_mutations.py` — editar/remover nós (arquivar skill = recuperável).

**O que criar (sem nome hermes):**
- `backend/app/services/preference_graph.py`
  - `build_graph(db) -> PreferenceGraph` — nós = `UserPreference` (F-010) + skills
    ativas; arestas de co-ocorrência (preferências reforçadas juntas) e de
    sobreposição lexical.
  - `mutate_preference(user_id, attr, action)` — editar/remover (espelha
    `learning_mutations`), com arquivamento recuperável.
  - Exporta JSON para o frontend desenhar o grafo na tela "Preferências Aprendidas"
    (PRD F-010 / UI §5).
- Reutiliza a tabela `user_preferences` já existente (não cria schema novo).

**Critérios de aceitação:**
- [ ] Grafo gerado a partir de `user_preferences` reais.
- [ ] Remoção de preferência arquiva (recuperável) e não apaga histórico.
- [ ] `pytest` cobre build + mutate.
- [ ] Sem nome hermes.

**Esforço:** ~9h (4h grafo + 3h mutate + 2h testes).

---

## 6. Memória de Aprendizado Incremental

**Problema:** lições de execuções passadas (ex: "Firecrawl caiu na porta 3022") não
são persistidas para orientar execuções futuras.

**O que reutilizar do hermes:**
- `memory_manager.py` + `memory_provider.py` — camada de memória (append/recupera
  chunks, provedor pluggável).
- `learning_mutations.py` — mutação de memórias.

**O que criar (sem nome hermes):**
- `backend/app/services/learning_memory.py`
  - `LearningMemory` — pequena camada que grava "lições" numa tabela SQLite
    `agent_lessons` (nova migration Alembic) ou num arquivo `data/agent_lessons.md`.
  - `record_lesson(agent, lesson)` / `recall_lessons(agent, k=5)`.
  - O orquestrador injeta lições relevantes no prompt dos agentes (estende
    `app/services/prompt_hydration.py`).
- Não usa `MEMORY.md`/`USER.md` do hermes — usa `data/agent_lessons.md` local.

**Critérios de aceitação:**
- [ ] Lição gravada é recuperada e injetada no prompt do agente correspondente.
- [ ] `pytest` com round-trip record/recall.
- [ ] Sem nome hermes.

**Esforço:** ~8h (3h camada + 3h injeção + 2h testes).

---

## 7. Orquestração Aprimorada (runtime helpers)

**Problema:** `orchestrator.py` é puro (máquina de estados). Falta lógica de runtime
para depurar fluxo, lidar com ciclos (Criação↔Revisão) e recovery.

**O que reutilizar do hermes:**
- `agent_runtime_helpers.py` — helpers de runtime/depuração de agentes (pause/resume,
  inspeção de estado).

**O que criar (sem nome hermes):**
- Estender `backend/app/services/orchestrator.py` com:
  - `resume_from_column(column)` — recalcula o agente e o estado ao retomar um card
    (útil após queda do backend).
  - `handle_review_cycle(card, review_passed)` — já existe `column_after_review`;
    adicionar logging estruturado do ciclo (Criação↔Revisão, Item B do PRD).
  - `inject_lessons_and_prefs(card, prompt)` — usa `learning_memory` + `preference_graph`.
- Sem copiar o `agent_runtime_helpers` inteiro (é gigante); só os helpers
  aplicáveis, renomeados.

**Critérios de aceitação:**
- [ ] Retomada de card após restart posiciona no agente correto.
- [ ] Ciclo de revisão logado; `pytest` cobre `resume_from_column`.
- [ ] Sem nome hermes.

**Esforço:** ~7h (3h helpers + 4h testes/integração).

---

## 8. Ordem de Execução (roadmap)

| Fase | Itens | Entrega |
|---|---|---|
| **Fase A** | 1 (Skill Factory) + 3 (Error Classifier/Backoff) | Base de resiliência + skills automáticas |
| **Fase B** | 2 (Compressão) + 7 (Orquestração) | Pipeline eficiente e retomável |
| **Fase C** | 4 (Metrics Insights) | Dashboard F-013 enriquecido |
| **Fase D** | 5 (Preference Graph) + 6 (Learning Memory) | Personalização F-010 + aprendizado |

Cada fase termina com `pytest` verde e atualização de `Conversa/handoff.md`.

---

## 9. Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Módulos do hermes têm imports pesados (`hermes_constants`, `agent.*`) | Copiar só a função/classe necessária, reescrever imports para o namespace do AgentFlow; validar com `python -c "import app.services.X"` |
| Sobreposição com código existente (circuit_breaker, orchestrator) | Estender, não duplicar; manter testes existentes passando |
| Custo de compressão/insights (chamadas LLM) | Usar modelo auxiliar barato; respeitar `BudgetLimit` (F-011) |
| Nome "hermes" vazando em skills geradas | `skill_factory` valida ausência da substring "hermes" no corpo antes de salvar |

## 10. Checklist de Aceite do Plano

- [ ] Toda capacidade mapeada para um arquivo concreto do AgentFlow
- [ ] Nenhum arquivo novo contém "hermes"
- [ ] Backend existente não é quebrado (testes atuais continuam verdes)
- [ ] Cada item tem critérios de aceitação testáveis
- [ ] Roadmap em 4 fases com entregáveis claros
