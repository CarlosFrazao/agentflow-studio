# Planejamento de Arquitetura — Fase 1 (AgentFlow Studio v1.1)

**Data:** 2026-07-11
**Autor:** Claude (Code), seguindo `CLAUDE.md` + skill `api-patterns` + skill `clean-code`
**Escopo:** Arquitetura base do MVP, divisão física de diretórios, modelo de dados (SQLite) e contrato de API (FastAPI/REST).
**Entregável desta fase:** Este documento + esqueleto de diretórios. Nenhum código de feature é implementado aqui.

---

## 1. Decisões de Arquitetura (checklist `api-patterns`)

| Pergunta | Decisão | Justificativa |
|---|---|---|
| Quem consome a API? | Frontend React (interno) + serviços externos (SRA/Firecrawl/GitHub) como clientes | Single-tenant local no MVP |
| Estilo de API | **REST** | Backend é Python/FastAPI (não monorepo TS → tRPC descartado); a `Spec_Tecnica_Integracao_v1_0.md` manda usar REST backend-a-backend para SRA/Firecrawl; GraphQL seria overkill (CRUD simples, sem over-fetching severo) |
| Envelope de resposta | `{ success, data | error, meta{ request_id, timestamp } }` | Padrão obrigatório da skill `api-patterns` (ver §3) |
| Versionamento | **URI** `/api/v1/...` | Produto v1; o mais simples e explícito |
| Autenticação | **MVP: nenhuma** (single-tenant local). Hooks reservados para API Key/JWT em v2 | PRD define single-tenant no MVP; o padrão `X-API-Key` do SRA já antecipa o modelo futuro |
| Rate limiting | Adiado (local single-tenant); estrutura deixa espaço para Token Bucket em v2 | api-patterns marca como recomendado p/ APIs públicas, não obrigatório p/ interna local |
| Documentação | Swagger automático do FastAPI em `/docs` | Zero custo, sempre sincronizado com o código |
| Tratamento de erro | Sempre explícito; nunca expor stack trace/SQL; códigos em `SCREAMING_SNAKE_CASE` | Regra inegociável da skill |

**Correções / decisões de integração (atualizado 2026-07-11):**
- Timeout de chamada MCP ao SRA = **90s** (PRD dizia 45s; `TIMEOUT_PER_SOURCE=30s` do SRA pode estourar 45s).
- Rede Docker: o AgentFlow **se junta à rede externa `firecrawl_backend`** já criada pelo Firecrawl (não cria `agentflow-net` própria).
- **SRA e Firecrawl são consumidos via MCP** (transporte SSE), conforme orientação explícita do usuário (HITL). Isso **reverte a decisão da `Spec_Tecnica_Integracao_v1_0.md`** (que mandava REST direto) e **retorna ao intento do ADR-005 do PRD** (MCP preferencial). Motivo do usuário: os dois serviços já rodam em containers próprios no Docker Desktop; o AgentFlow apenas conecta-se a eles como cliente MCP — não os incorpora.
  - SRA expõe MCP em `/mcp/sse` (✅ confirmado na Spec).
  - Firecrawl expõe MCP/REST (PRD §4.3); **URL exata do endpoint MCP do Firecrawl a confirmar** no container dele.
  - Conexão é **remota (SSE)**, não subprocesso STDIO — os servidores já estão no ar.
- **GitHub API continua REST direto** (não há servidor MCP do GitHub no setup; é API pública).
- Porta Firecrawl: confirmar `3002` (container) vs `3022` (host) no `docker-compose.yaml` do Firecrawl antes de fixar a URL.

---

## 2. Divisão Física de Diretórios

```
AgentFlow Studio/
├── Cria/                       # PRD, Specs, este plano (docs de requisito)
├── Claude/                     # Guias Claude Code (existente)
├── Conversa/                   # handoff.md + chat_log.md (criar na Fase 1.5)
├── data/                       # SQLite (agentflow.db) — gitignored
├── backend/
│   ├── app/
│   │   ├── main.py             # App factory, CORS, inclusão de routers
│   │   ├── core/
│   │   │   ├── config.py       # pydantic-settings (SRA_BASE_URL, FIRECRAWL_BASE_URL, timeouts, GEMINI_API_KEY...)
│   │   │   ├── database.py     # engine + session (SQLite)
│   │   │   ├── responses.py    # helpers do envelope padrão
│   │   │   └── security.py     # (futuro) auth hooks
│   │   ├── models/             # ORM SQLAlchemy (1 arquivo por entidade)
│   │   ├── schemas/            # Pydantic request/response
│   │   ├── api/v1/             # routers versionados
│   │   │   ├── router.py       # agregador
│   │   │   ├── cards.py
│   │   │   ├── projects.py
│   │   │   ├── artifacts.py
│   │   │   ├── executions.py
│   │   │   ├── snippets.py
│   │   │   ├── preferences.py
│   │   │   └── budget.py
│   │   ├── services/
│   │   │   ├── orchestrator.py # máquina de estados do pipeline (Backlog→...→Done)
│   │   │   ├── llm.py          # wrapper Gemini 2.5 Pro
│   │   │   ├── preferences.py  # inferência/applicação de preferências
│   │   │   └── agents/         # ideation, research, planner, reviewer, dev (F-002..F-006)
│   │   └── clients/            # integrações externas (SRA/Firecrawl por MCP, GitHub por REST)
│   │       ├── mcp/
│   │       │   ├── base.py       # conexão SSE cliente MCP genérica (remote)
│   │       │   ├── sra_client.py # ferramentas do SRA expostas via MCP
│   │       │   └── firecrawl_client.py # ferramentas do Firecrawl via MCP
│   │       ├── github_client.py   # REST direto (API pública, sem MCP)
│   │       └── circuit_breaker.py # degradação graciosa p/ SRA/Firecrawl/GitHub
│   ├── tests/                  # pytest (backend)
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/kanban/  # colunas, card, badge auto-aprovado, modal de aprovação
│   │   ├── pages/              # board, configurações, dashboard
│   │   ├── stores/             # Zustand
│   │   ├── api/                # hooks TanStack Query + fetch wrapper (respeita envelope)
│   │   └── types/              # tipos espelhando o contrato
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── sandbox/
│   ├── validate.py             # recebe código gerado, roda em container efêmero (sem rede)
│   └── Dockerfile.sandbox
└── docker-compose.yml          # junta-se a firecrawl_backend (external)
```

---

## 3. Modelo de Dados (SQLite / SQLAlchemy)

Entidades do PRD v1.1 (+ adições F-010/F-011 + cache F-003/F-008). UUID como PK; timestamps em UTC.

**User**
- `id` UUID PK · `email` · `display_name` · `created_at` · `updated_at`

**Project**
- `id` UUID PK · `user_id` FK→User · `name` · `description` · `status` · `created_at` · `updated_at`

**Card** (coração do Kanban)
- `id` UUID PK · `project_id` FK→Project · `column` enum[backlog, researching, planning, reviewing, production, done] · `title` · `order_index` int · `confidence_score` float (0–1) · `approval_by` enum[human, auto, none] · `auto_approved` bool · `revert_deadline` datetime (janela 30min p/ auto-approve) · `created_at` · `updated_at`

**Artifact** (saída dos agentes, salva como `type=markdown/json/code`)
- `id` UUID PK · `card_id` FK→Card · `agent_name` · `type` enum[markdown, json, code] · `content` Text · `created_at`

**Execution** (métricas de tempo/custo por agente)
- `id` UUID PK · `card_id` FK→Card · `agent_name` · `status` enum[pending, running, success, failed] · `duration_ms` int · `cost_usd` float · `started_at` · `finished_at` · `error_message` Text nullable

**Snippet** (F-009, com licença obrigatória)
- `id` UUID PK · `user_id` FK→User · `title` · `content` Text · `language` · `license` enum[MIT, Apache-2.0, BSD, GPL, AGPL, unknown, proprietary] · `source_url` · `created_at`

**UserPreference** (F-010)
- `id` UUID PK · `user_id` FK→User · `attribute` (ex: preferred_testing_framework) · `value` · `confidence_count` int (só aplica se ≥2) · `last_reinforced_at` · `created_at` · `updated_at`

**BudgetLimit** (F-011)
- `id` UUID PK · `user_id` FK→User · `monthly_limit_usd` float (default 10) · `per_project_limit_usd` float (default 3) · `current_month_spend_usd` float · `updated_at`

**ResearchCache** (F-003/F-008 — evita rechamar SRA)
- `id` UUID PK · `query_hash` String UNIQUE · `source` enum[sra, code_research] · `result` Text · `created_at` · `expires_at` (7 dias)

---

## 4. Contrato de API (REST, `/api/v1`)

### 4.1 Cards (Kanban)
| Método | Rota | Ação |
|---|---|---|
| GET | `/cards?project_id=&column=&page=&per_page=` | Listar (paginação offset) |
| POST | `/cards` | Criar card (nova ideia bruta) |
| GET | `/cards/{id}` | Detalhe (com artifacts + última execution) |
| PATCH | `/cards/{id}` | Mover coluna / editar título |
| DELETE | `/cards/{id}` | Remover |
| POST | `/cards/{id}/run` | Orquestrador roda o agente da coluna atual → retorna card + artifacts + executions |
| POST | `/cards/{id}/approve` | HITL aprovação humana |
| POST | `/cards/{id}/reject` | Rejeição (alimenta UserPreference) |
| POST | `/cards/{id}/revert` | Desfaz auto-approve dentro da janela de 30min |

### 4.2 Demais recursos
- **Projects:** `GET/POST /projects`, `GET/PATCH /projects/{id}`
- **Artifacts:** `GET/POST /cards/{id}/artifacts`
- **Executions:** `GET /executions?card_id=&agent=&status=` (tabela do dashboard)
- **Snippets (F-009):** `GET /snippets`, `POST /snippets` (exige `license`), `DELETE /snippets/{id}`
- **Preferences (F-010):** `GET /users/{id}/preferences`, `PATCH /users/{id}/preferences/{attribute}`
- **Budget (F-011):** `GET /users/{id}/budget`, `PUT /users/{id}/budget`

**Research cache** e **clientes MCP externos** são camada de serviço — não expostos como recurso direto no MVP (podem ganhar endpoint de debug em v1.2).

### 4.3b Integração SRA/Firecrawl via MCP (SSE remoto)

Os agentes que precisam de pesquisa (Research F-003) e de coleta web (Code Research F-008) consomem SRA e Firecrawl **como clientes MCP remotos (transporte SSE)** — os servidores já rodam nos containers do usuário no Docker Desktop. O AgentFlow **não os incorpora nem os sobe**.

- `SRA_MCP_URL` (ex: `http://sra-app:3458/mcp/sse` dentro da rede Docker; `http://localhost:3458/mcp/sse` no dev local)
- `FIRECRAWL_MCP_URL` (a confirmar no container do Firecrawl — PRD diz MCP/REST; SSE é o alvo)
- `GITHUB_TOKEN` (REST direto, sem MCP)
- Timeout por chamada de ferramenta MCP: **90s** (SRA).
- Cada cliente MCP herda o `CircuitBreaker` (abre após 3 falhas, 60s) — ver `clients/circuit_breaker.py`.
- Se SRA indisponível: Research Agent salva card com aviso "pesquisa de mercado incompleta" e segue (degradação graciosa, PRD F-003).

### 4.3 Envelope (obrigatório)

Sucesso:
```json
{ "success": true, "data": { "...": "..." },
  "meta": { "request_id": "req_7f3a9b2c", "timestamp": "2026-07-11T10:30:00Z" } }
```
Erro:
```json
{ "success": false,
  "error": { "code": "VALIDATION_ERROR", "message": "...",
             "details": [ { "field": "...", "issue": "..." } ] },
  "meta": { "request_id": "req_...", "timestamp": "..." } }
```
Regras: `success` sempre presente; `data` só em sucesso; `error.code` em `SCREAMING_SNAKE_CASE`; `meta.request_id` sempre presente; nunca expor SQL/stack.

### 4.4 Status codes principais
`200` leitura · `201` criado · `204` sem conteúdo · `400` malformado · `401` não autenticado (v2) · `403` sem permissão (v2) · `404` não encontrado · `409` conflito de estado (ex: card já naquela coluna) · `422` erro semântico de validação · `429` rate limit (v2) · `500` erro interno.

---

## 5. Próximos Passos (transição Fase 1 → Fase 2)

> **Decisão do usuário (2026-07-11):** SRA e Firecrawl **não** entram neste repositório — já rodam no Docker Desktop dele e são consumidos via **MCP (SSE remoto)**. O AgentFlow só conecta-se a eles como cliente. **Não** é necessário subir/clonar SRA+Firecrawl neste projeto. O único item a confirmar é a **URL exata do endpoint MCP SSE de cada um** (SRA `/mcp/sse` confirmado; Firecrawl a confirmar).

1. Criar `backend/pyproject.toml`, `requirements.txt` (inclui `mcp` SDK + `httpx` + `sqlalchemy` + `fastapi` + `pydantic-settings`), `app/core/config.py`, `database.py`, `responses.py`.
2. Implementar os 9 modelos SQLAlchemy + `schemas/` + bootstrap `create_all`.
3. Implementar `clients/mcp/base.py` (conexão SSE cliente MCP genérica, remota) + `sra_client.py` + `firecrawl_client.py` + `github_client.py` (REST) + `circuit_breaker.py`. Testes de timeout/circuit-breaker (Cobertura alvo: 80%).
4. Implementar routers `v1` + orquestrador (máquina de estados) com testes pytest.
5. `handoff.md` e `chat_log.md` já criados nesta Fase 1 (HANDOFF-AUDIT concluído).

---

## 6. Checklist de Qualidade (pré-Fase 2)
- [x] Estilo de API decidido e justificado (REST)
- [x] Envelope de resposta/erro definido
- [x] Versionamento documentado (/api/v1)
- [x] Estratégia de auth decidida (nula no MVP, hook p/ v2)
- [x] Rate limiting previsto (adiado, com espaço)
- [x] Documentação em /docs definida
- [x] Modelo de dados completo (9 entidades) espelhando PRD
- [x] Diretórios fisicamente estruturados
- [x] **SRA/Firecrawl via MCP (SSE) — decisão do usuário registrada** (reverte Spec, retoma ADR-005)
- [ ] Confirmar `FIRECRAWL_MCP_URL` exato no container do Firecrawl (SRA `/mcp/sse` já confirmado)
- [ ] Confirmar rede `firecrawl_backend` (external) no `docker-compose.yml` do AgentFlow
