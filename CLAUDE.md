# CLAUDE.md — AgentFlow Studio v1.2 (Governança Universal)

> **Guia Operacional do Claude Code:** [Guia Parte 1](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Claude/CLAUDE_CODE_GUIDE_part1.md) | [Guia Parte 2](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Claude/CLAUDE_CODE_GUIDE_part2.md)

---

## 🔴 MISSÃO ATUAL — Plano de Integração de Inteligência de Agentes

> [!IMPORTANT]
> **Status: Todas as Fases de Melhorias de IA estão CONCLUÍDAS ✅**
> O MVP do AgentFlow Studio está completo. A próxima atividade recomendada é:
> **validação visual e de smoke test** via o Protocolo ARES (ver Seção 🎯 abaixo).
> **Regra Suprema de Geração:** Nenhum arquivo novo do AgentFlow pode conter a substring `hermes`
> (nem em nome, nem em imports, nem em comentários, nem no corpo de skills geradas).

### 📄 Arquivos de Requisitos (LEIA ANTES DE ESCREVER CÓDIGO):
* **[00_Indice_Fases.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Planos_Melhorias/00_Indice_Fases.md)** — Índice Geral e ordem recomendada das fases
* **[PLANO_COMPLETO.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Planos_Melhorias/PLANO_COMPLETO.md)** — Plano Geral de Melhorias
* **[PRD_AgentFlow_Studio_v1_1.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Cria/PRD_AgentFlow_Studio_v1_1.md)** — Especificação de Requisitos do MVP
* **[Spec_Tecnica_Integracao_v1_0.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Cria/Spec_Tecnica_Integracao_v1_0.md)** — Especificação de Integração ↔ SRA ↔ Firecrawl

---

## 📁 Arquivos Ativos de Memória e Log do Projeto

| Arquivo | Caminho Absoluto |
|---------|------------------|
| **Chat Log ativo** | [chat_log.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Conversa/chat_log.md) |
| **Handoff ativo** | [handoff.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Conversa/handoff.md) |
| **File Map** | [file_map.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Conversa/file_map.md) |
| **Napkin ativo** | [napkin.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.antigravity/napkin.md) |

---

## 🗄️ Stack de Tecnologia Implementada

| Camada | Tecnologia |
|--------|------------|
| **Backend** | Python 3.12 / FastAPI (API REST, integração HTTP/MCP com SRA, Firecrawl e GitHub via `backend/`) |
| **Frontend** | React 19 / TypeScript / Vite / Tailwind CSS (Kanban + Dashboard em `frontend/`) |
| **Frontend Estático** | HTML/JS puro em `frontend_static/` — servido em same-origin pelo FastAPI via StaticFiles |
| **Banco de Dados** | SQLite assíncrono (`backend/data/agentflow.db`) via SQLAlchemy + Alembic migrations |
| **LLM Multi-provider** | OpenRouter → Groq → Gemini → Ollama (fallback automático em `backend/app/services/llm.py`) |
| **Clients MCP** | SRA (`sra-app:3458`) e Firecrawl (`firecrawl-api-new:3002`) — conexão SSE remota, não embutida |
| **Client REST** | GitHub API direta (`api.github.com`) com circuit breaker + retry |
| **Infra** | Docker Compose (`docker-compose.yml`), rede externa `firecrawl_backend` |
| **Qualidade** | `pytest` (backend, 244+ testes) e `Vitest` (frontend) |

---

## 🎯 PROTOCOLO DE VALIDAÇÃO VISUAL — ARES ENGINE (OBRIGATÓRIO)

> [!CAUTION]
> **R33 — NAVEGADOR INTEGRADO PROIBIDO (P0):** É TERMINANTEMENTE PROIBIDO usar
> `browser_subagent` ou qualquer ferramenta de navegador da IDE.
> Use EXCLUSIVAMENTE os scripts Playwright locais do `Ambiente Testes/`.

### Arquivo de Instruções Completo:
* **[DEPLOY_E_VALIDACAO_AGENTFLOW.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Ambiente%20Testes/DEPLOY_E_VALIDACAO_AGENTFLOW.md)**
  — Protocolo passo a passo para subir o projeto e validar via ARES.

### Fluxo Resumido (3 passos):
```
1. Subir o app:
   docker compose up --build -d
   (ou: uvicorn no backend + npm run dev no frontend)

2. Configurar o .env do Ambiente Testes:
   APP_URL=http://localhost:5173
   EMAIL_SELECTOR=        ← vazio = sem login (acesso direto)

3. Abrir o Navegador ARES:
   cd "f:\Criando sites pelo pc\Site AgentFlow Studio\Ambiente Testes"
   node logic/ares-visual-standard.js
```

### Estrutura do `Ambiente Testes/`:

| Diretório/Arquivo | Função |
|-------------------|--------|
| `logic/ares-visual-standard.js` | **Script principal** — abre Chromium visual, navega até o APP_URL, grava logs |
| `logic/ares-visual-pentest.js` | Auditoria de segurança passiva (headers, cookies, erros HTTP) |
| `logic/ares-visual-audit.js` | Auditoria funcional de UI |
| `Evidencias/` | Onde salvar screenshots e vídeos de validação formal |
| `screenshots/` | Screenshots automáticos do `ares-visual-standard.js` |
| `reports/` | Relatórios de segurança do pentest |
| `logs/browser_run.log` | Log detalhado de cada sessão do navegador ARES |
| `.env` | Configurações: `APP_URL`, `EMAIL_SELECTOR`, `TEST_EMAIL`, etc. |
| `START_BROWSER_DASHBOARD.bat` | Atalho para abrir ARES sem autenticação |
| `START_BROWSER_PENTEST.bat` | Atalho para rodar auditoria de segurança |
| `IA_LEIA-ME_PRIMEIRO.md` | Mandato ARES e regras de uso do ambiente |
| `PASSO_A_PASSO_NAVEGADOR_ARES.md` | Guia passo a passo de uso do ambiente |

---

## 🌐 Topologia de Serviços Externos (MCP via Docker Desktop)

> Os containers SRA e Firecrawl são **externos** a este projeto — NÃO estão no `docker-compose.yml`.
> Eles rodam em seus próprios Docker Composes separados e o AgentFlow os consome como **clientes MCP/REST**.

| Serviço | URL Interna (Docker) | Uso |
|---------|----------------------|-----|
| **Smart Research Agent (SRA)** | `http://sra-app:3458/mcp/sse` | Pesquisa profunda multi-fonte (GitHub, Reddit, HN, ArXiv, etc.) |
| **Firecrawl** | `http://firecrawl-api-new:3002/mcp/sse` | Scraping web + bypass de WAF |
| **Firecrawl REST** | `http://firecrawl-api-new:3002` | Fallback REST do Firecrawl |
| **AgentFlow Backend** | `http://localhost:8000` | API FastAPI deste projeto |
| **AgentFlow Frontend** | `http://localhost:5173` | App React/Vite |

**Rede Docker compartilhada:** `firecrawl_backend` (externa, criada pelo Firecrawl Compose)

---

## 🧠 Habilidades Locais Portáveis Ativas (Local Skills)

> [!IMPORTANT]
> **REGRA ABSOLUTA DE CARREGAMENTO DE SKILLS:**
> Skills estão em `F:\Criando sites pelo pc\Site AgentFlow Studio\.claude\skills\`
> Leia a `SKILL.md` correspondente **imediatamente antes de codificar**.

### Catálogo Completo de Skills Disponíveis:

| Skill | Localização | Quando Usar |
|-------|-------------|-------------|
| `python-pro` | `.claude/skills/python-pro/` | Qualquer task Python/FastAPI |
| `api-patterns` | `.claude/skills/api-patterns/` | Novos endpoints, schemas, routers |
| `clean-code` | `.claude/skills/clean-code/` | Refatoração, SOLID, legibilidade |
| `test-driven-development` | `.claude/skills/test-driven-development/` | TDD Red→Green, fixtures pytest |
| `multi-agent-patterns` | `.claude/skills/multi-agent-patterns/` | Orquestrador, agentes, pipelines |
| `http-request-mastery` | `.claude/skills/http-request-mastery/` | Clientes HTTP, circuit breaker, retry |
| `web-scraping-resilience` | `.claude/skills/web-scraping-resilience/` | Integração SRA/Firecrawl |
| `ui-ux-pro-max` | `.claude/skills/ui-ux-pro-max/` | Frontend React, Tailwind, UX |
| `javascript-mastery` | `.claude/skills/javascript-mastery/` | JS/TS avançado |
| `css-mastery` | `.claude/skills/css-mastery/` | CSS avançado, animações |
| `docker-expert` | `.claude/skills/docker-expert/` | Docker, Compose, redes |
| `firecrawl-extractor` | `.claude/skills/firecrawl-extractor/` | Uso do MCP Firecrawl |
| `security-hardening` | `.claude/skills/security-hardening/` | OWASP, headers, auth |
| `systematic-debugging` | `.claude/skills/systematic-debugging/` | Debug metódico |
| `root-cause-analysis` | `.claude/skills/root-cause-analysis/` | Diagnóstico de causa raiz |
| `scientific-method-empiricism` | `.claude/skills/scientific-method-empiricism/` | Validação empírica |
| `agent-evaluation` | `.claude/skills/agent-evaluation/` | QA de agentes IA |
| `python-patterns` | `.claude/skills/python-patterns/` | Padrões avançados Python |
| `prompt-engineering` | `.claude/skills/prompt-engineering/` | Construção de prompts LLM |
| `mcp-server-development` | `.claude/skills/mcp-server-development/` | Criar servidores MCP |
| `local-llm-orchestrator` | `.claude/skills/local-llm-orchestrator/` | Ollama e LLMs locais |

### Mapeamento de Skills por Fase:

| Tarefa / Fase | Skills a Carregar ANTES de codificar |
|---|---|
| **Fase A1: Skill Factory** | `python-pro` + `clean-code` + `api-patterns` |
| **Fase A2: Classificador de Erros & Backoff** | `python-pro` + `http-request-mastery` + `web-scraping-resilience` |
| **Fase B1: Compressão de Artefatos** | `python-pro` + `multi-agent-patterns` |
| **Fase B2: Orquestração Aprimorada** | `python-pro` + `multi-agent-patterns` |
| **Fase C1: Motor de Métricas & Dashboard** | `python-pro` + `api-patterns` + `ui-ux-pro-max` |
| **Fase D1: Grafo de Preferências** | `python-pro` + `api-patterns` |
| **Fase D2: Memória de Aprendizado** | `python-pro` + `multi-agent-patterns` |
| **Deploy / Docker** | `docker-expert` |
| **Validação Visual (ARES)** | `javascript-mastery` + `systematic-debugging` |
| **Segurança / Pentest** | `security-hardening` |

---

## 🚨 REGRAS ABSOLUTAS DE EXECUÇÃO (VIGILÂNCIA ZEUS & KARPATHY RIGOR)

### 1. Protocolo de Inicialização OBRIGATÓRIO (Passo Zero)
Ao iniciar a sessão:
1. Leia `Conversa/handoff.md` para saber o estado atual do projeto.
2. Leia `Conversa/chat_log.md` (últimas 10 entradas) para continuidade.
3. Leia `Cria/PRD_AgentFlow_Studio_v1_1.md` e a Fase ativa correspondente em `Planos_Melhorias/`.
4. Carregue as skills correspondentes à tarefa atual de forma atômica e sob demanda.
5. Declare qual FASE e TAREFA irá executar antes de codificar.

### 2. Rigor Karpathy de Vibe Coding
* **Código Mínimo:** Faça modificações cirúrgicas. Nunca crie complexidade desnecessária.
* **Zero Assunções Silenciosas:** Em caso de ambiguidade ou tradeoffs, PARE imediatamente e pergunte ao usuário.
* **Critérios de Sucesso:** Defina os testes de unidade no `pytest` antes de escrever o código.
* **Anti-TODO:** É PROIBIDO entregar código com `# TODO`, `# FIXME` ou `# HACK`.

### 3. Framework ZEUS de Vigilância por Blocos
* **PRE-CHECK:** As dependências do bloco estão satisfeitas? Li as skills correspondentes?
* **MID-CHECK:** Código entregue completo, sem TODOs e sem imports redundantes?
* **POST-CHECK (Anti-Padrões):** Varredura Anti-TODO (`grep -rn "TODO\|FIXME\|HACK" backend/app/`), Anti-Botão-Morto e Prova de Vida (rodar pytest).
* **HANDOFF-AUDIT:** Atualizou `Conversa/chat_log.md` e `Conversa/handoff.md` com o formato padrão de handoff?

### 4. Regras de Segurança
* **Sem substring `hermes`:** Grep 0 em todos os arquivos novos/modificados.
* **Sem credentials hardcoded:** Usar `.env` exclusivamente.
* **Sem `browser_subagent`:** Usar `node logic/ares-visual-standard.js` (R33).

### 5. Idioma de Comunicação (PT-BR)
* Responder e comunicar EXCLUSIVAMENTE em Português do Brasil (PT-BR).
* Código, comentários técnicos e especificações: em Inglês (EN).

---

## 📊 Status das Features do MVP (Kanban)

| ID | Feature / Componente | Status |
|---|---|---|
| **F-001** | Pipeline Kanban Visual | [x] **Concluída** |
| **F-002** | Ideation Agent | [x] **Concluída** |
| **F-003** | Research Agent (SRA Integration) | [x] **Concluída** |
| **F-004** | Planner Agent | [x] **Concluída** |
| **F-005** | Reviewer Agent (Leve) | [x] **Concluída** |
| **F-006** | Dev Agent + Sandbox Validadora | [x] **Concluída** |
| **F-007** | Human-in-the-Loop Gate (Auto-approve) | [x] **Concluída** |
| **F-008** | Code Research Agent (GitHub + Firecrawl) | [x] **Concluída** |
| **F-009** | Snippet Library | [x] **Concluída** |
| **F-010** | Perfil de Preferências do Usuário | [x] **Concluída** |
| **F-011** | Cap de Orçamento por Projeto | [x] **Concluída** |
| **F-012** | Onboarding Interativo | [ ] **Pendente** |
| **F-013** | Dashboard de Métricas e Custos v1.2 | [x] **Concluída** |

---

## 📋 Status das Fases de Melhorias (Planos_Melhorias)

- [x] **Fase A1**: Skill Factory (Gerador de Habilidades Dinâmicas) | [Concluída]
- [x] **Fase A2**: Classificador de Erros & Backoff | [Concluída]
- [x] **Fase B1**: Compressão de Artefatos | [Concluída]
- [x] **Fase B2**: Orquestração Aprimorada e Retomável | [Concluída]
- [x] **Fase C1**: Motor de Métricas e Insights do Dashboard | [Concluída]
- [x] **Fase D1**: Grafo de Preferências do Usuário (F-010) | [Concluída]
- [x] **Fase D2**: Memória de Aprendizado Incremental | [Concluída]

```
[x] = Concluído | [/] = Em Andamento | [ ] = Pendente
```

---

## 🗺️ Mapa da Estrutura do Projeto

```
Site AgentFlow Studio/
├── backend/                    ← FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/v1/             ← Routers (projects, cards, users, preferences, metrics...)
│   │   ├── core/               ← config.py, database.py, exceptions.py, logging.py
│   │   ├── models/             ← SQLAlchemy models (Card, Project, User, UserPreference...)
│   │   ├── schemas/            ← Pydantic schemas
│   │   ├── services/           ← orchestrator, llm, agents, preference_graph, learning_memory...
│   │   └── clients/            ← mcp/ (SRA, Firecrawl), circuit_breaker, retry, error_classifier
│   ├── alembic/versions/       ← Migrations do banco
│   ├── data/                   ← agentflow.db (SQLite) + agent_lessons.md
│   ├── tests/                  ← Suite pytest (244+ testes)
│   ├── .env                    ← Variáveis de ambiente (chaves LLM, URLs)
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   ← React 19 + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/         ← KanbanBoard, Dashboard, InsightsPanel...
│   │   └── lib/client.ts       ← Fetch wrapper autenticado
│   └── Dockerfile
│
├── frontend_static/            ← HTML/JS puro (versão legada, servida em same-origin)
│   └── index.html
│
├── Ambiente Testes/            ← Navegador ARES + scripts Playwright de validação
│   ├── logic/
│   │   ├── ares-visual-standard.js    ← SCRIPT PRINCIPAL de validação visual
│   │   ├── ares-visual-pentest.js     ← Auditoria de segurança passiva
│   │   └── ares-visual-audit.js       ← Auditoria funcional
│   ├── Evidencias/             ← Screenshots/vídeos de validação formal
│   ├── screenshots/            ← Screenshots automáticos do ARES
│   ├── reports/                ← Relatórios de segurança
│   ├── logs/                   ← browser_run.log
│   ├── .env                    ← APP_URL, EMAIL_SELECTOR, TEST_EMAIL...
│   ├── DEPLOY_E_VALIDACAO_AGENTFLOW.md ← Instruções de deploy e validação
│   ├── IA_LEIA-ME_PRIMEIRO.md
│   └── PASSO_A_PASSO_NAVEGADOR_ARES.md
│
├── Planos_Melhorias/           ← Documentos de especificação das fases A→D
├── Cria/                       ← PRD, Spec Técnica e artefatos de planejamento
├── Conversa/                   ← Memória: handoff.md, chat_log.md, file_map.md
├── Claude/                     ← Guias do Claude Code (CLAUDE_CODE_GUIDE_part1/2.md)
├── .claude/
│   ├── skills/                 ← 21 skills locais portáteis
│   └── settings.json           ← Configuração do Claude Code (modelo, excludePatterns, hooks)
├── docker-compose.yml          ← Orquestração Docker (backend + frontend)
└── CLAUDE.md                   ← Este arquivo (governança universal)
```

---

## ⚡ COMANDOS RÁPIDOS DE REFERÊNCIA

```powershell
# Subir o projeto completo
cd "f:\Criando sites pelo pc\Site AgentFlow Studio"
docker compose up --build -d

# Rodar testes backend
cd "f:\Criando sites pelo pc\Site AgentFlow Studio\backend"
pytest -q

# Abrir navegador ARES
cd "f:\Criando sites pelo pc\Site AgentFlow Studio\Ambiente Testes"
node logic/ares-visual-standard.js

# Auditoria de segurança
node logic/ares-visual-pentest.js

# Ver logs dos containers
docker compose logs -f

# Derrubar o projeto
docker compose down
```

---
*Atualizado por: @ceo-agent (Antigravity IDE) — 2026-07-14*
*Sincronizado com: `Conversa/handoff.md` · `Conversa/chat_log.md` · `Ambiente Testes/DEPLOY_E_VALIDACAO_AGENTFLOW.md`*
