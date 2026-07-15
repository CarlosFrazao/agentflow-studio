# Product Requirements Document (PRD)

## AgentFlow Studio v1.1 — MVP (Revisado)

**Document Version:** 1.1
**Date:** 2026-07-10
**Status:** Em Revisão — Aguardando Aprovação
**Author:** Revisão colaborativa (Claude + User), a partir do PRD v1.0 (PRD Agent v2.0)
**Reviewers:** User (Human-in-the-Loop)

---

## 0. Changelog v1.0 → v1.1

| # | Mudança | Motivo |
|---|---------|--------|
| 1 | **Research Agent volta ao escopo do MVP** (era ausente no v1.0) | Delegado ao Smart Research Agent (SRA) via MCP/REST — custo de engenharia baixo, ganho de qualidade alto |
| 2 | **Code Research Agent (versão enxuta) entra no MVP** — antes era F-010, adiada para v1.5 | Viável com GitHub API + Firecrawl self-hosted + 1-2 chamadas de LLM; não precisa de AST parsing/embeddings pra v1 |
| 3 | **Reviewer Agent (versão leve) volta ao MVP** | Era o "seguro de qualidade" da ideia original; barato (1 chamada de validação) |
| 4 | **Perfil de Preferências do Usuário** (nova feature) | Fecha o ciclo de personalização: aprovações/rejeições alimentam execuções futuras |
| 5 | **Sandbox de validação do código gerado** (nova feature) | Dev Agent passa a validar que o código roda antes de entregar |
| 6 | **Métricas de tempo divididas** em "tempo de processamento do agente" vs. "tempo total incl. aprovação humana" | v1.0 tinha meta de <15min inconsistente com timeout de aprovação de 24h |
| 7 | **Cap de orçamento por usuário/projeto** (nova feature) | Proteção contra custo descontrolado de API |
| 8 | **Campo de licença em Snippet e nos resultados do Code Research Agent** | Segurança jurídica no reuso de código de terceiros |
| 9 | **Onboarding Interativo (F-008) e Dashboard de Métricas completo (F-009) rebaixados de P0→P1/adiados** | Não testam a hipótese central; liberam tempo de engenharia pras features acima |
| 10 | **3 novos ADRs** (integração SRA, integração Firecrawl, auto-approve por confidence) | Documentar decisões de arquitetura desta revisão |

---

## 1. Visão Geral

### 1.1 Propósito

O AgentFlow Studio é uma plataforma de orquestração multi-agente com interface Kanban visual que transforma ideias brutas em produtos digitais prontos para deploy. Cada card do Kanban representa uma ideia em evolução, passando por agentes especializados que pesquisam, planejam, revisam e codificam — com aprovação humana nas transições de fase e, quando a confiança do agente é alta, aprovação automática opcional.

Diferente do v1.0, o AgentFlow Studio **não tenta ser autossuficiente em pesquisa e coleta web** — ele orquestra duas ferramentas próprias já em desenvolvimento (Smart Research Agent e Firecrawl self-hosted) em vez de reimplementar essa infraestrutura.

### 1.2 Ecossistema de Ferramentas (novo)

| Ferramenta | Papel no AgentFlow Studio | Como se conecta |
|---|---|---|
| **AgentFlow Studio** | Orquestrador do pipeline + Kanban + HITL gates | — |
| **Smart Research Agent (SRA)** | Pesquisa de mercado e concorrentes multi-fonte (GitHub, Reddit, HN, ArXiv, ProductHunt) com ranking de qualidade e detecção de gaps | MCP (preferencial) ou REST, container próprio |
| **Firecrawl (self-hosted)** | Engine de coleta web (scrape/crawl/map) para fontes fora do GitHub — docs, blogs técnicos, changelogs | MCP ou REST, container próprio; também já usado internamente pelo SRA |
| **GitHub API** | Busca de repositórios + leitura de arquivos brutos de código | REST direto (mais rápido/barato que Firecrawl para este caso específico) |

### 1.3 Escopo

#### In-Scope (v1.1 MVP)

| ID | Feature | Descrição | Mudança vs v1.0 |
|----|---------|-----------|------------------|
| F-001 | Pipeline Kanban Visual | Board com 6 colunas (Backlog, Researching, Planning, Reviewing, Production, Done) | Coluna "Reviewing" volta ao board |
| F-002 | Ideation Agent | Ideia bruta → JSON estruturado | Sem mudança |
| F-003 | Research Agent | Delega ao SRA (mercado/concorrentes) + orquestra Code Research Agent (código reutilizável) | **Novo no MVP** |
| F-004 | Planner Agent | Plano de execução com fases, milestones, stack, riscos | Agora recebe também o output do Research Agent |
| F-005 | Reviewer Agent (leve) | Audita consistência entre Ideia → Pesquisa → Plano antes de codar | **Volta ao MVP** |
| F-006 | Dev Agent | Gera código + valida em sandbox antes de entregar | Adição do passo de sandbox |
| F-007 | Human-in-the-Loop Gate | Aprovação manual OU automática (se confidence score alto) | Adição do auto-approve |
| F-008 | Code Research Agent (enxuto) | GitHub API + Firecrawl + LLM → sugere arquivos/padrões reutilizáveis, com checagem de licença | **Novo, substitui o antigo F-006 "GitHub Search Básico"** |
| F-009 | Snippet Library | Catalogação de snippets, agora com campo de licença | Campo `license` adicionado |
| F-010 | Perfil de Preferências do Usuário | Aprendizado incremental de preferências de stack/estilo a partir de aprovações e edições | **Novo** |
| F-011 | Cap de Orçamento | Limite de gasto configurável por usuário e por projeto | **Novo** |
| F-012 | Onboarding Interativo | Tutorial de primeiro uso | Rebaixado para P1 |
| F-013 | Dashboard de Métricas | Métricas de uso, tempo, custo | Rebaixado para P1, versão simplificada no MVP |

#### Out-of-Scope (v1.1 — Futuro)

| ID | Feature | Motivo do Deferimento | Versão Alvo |
|----|---------|----------------------|-------------|
| F-014 | Code Archaeologist Completo (AST + embeddings + análise semântica profunda) | A versão enxuta (F-008) já cobre 80% do valor com 20% do esforço | v1.5 |
| F-015 | Multi-Provider IA (LiteLLM) | Complexidade desnecessária no MVP | v1.2 |
| F-016 | Real-time Collaboration | Multi-usuário não necessário para validação de conceito | v2.0 |
| F-017 | Agent Store / Marketplace | Requer comunidade estabelecida | v2.0 |
| F-018 | Mobile App Nativo | Web responsivo cobre o público-alvo | v2.0 |
| F-019 | Enterprise Features (SSO, RBAC, Audit) | Público-alvo é indie hackers | v2.0 |
| F-020 | Billing / Payments | Freemium sem pagamento no MVP | v1.2 |
| F-021 | Eval framework completo (golden set automatizado, CI de qualidade de prompt) | Necessário mas pode começar manual no MVP; automatizar em v1.2 | v1.2 |

### 1.4 Público-Alvo

Sem mudanças em relação ao v1.0: desenvolvedores solo/indie hackers (primário), pequenas equipes de startup (secundário), agências (terciário).

### 1.5 Métricas de Sucesso (revisado)

O v1.0 tinha uma meta de "<15 min de ideia a código" que conflitava com o timeout de 24h do gate de aprovação humana. A v1.1 separa isso em duas métricas distintas:

| Métrica | Target | Como Medir |
|---------|--------|-----------|
| **Tempo de processamento dos agentes** (soma de execução, sem esperar humano) | < 8 min | Soma de `duration_ms` de todas as Execution de um projeto |
| **Tempo total ideia → código** (incluindo aprovações humanas) | < 45 min para projetos simples com auto-approve; sem meta rígida para projetos complexos com revisão manual | Timestamp de criação do card vs. chegada em "Done" |
| Taxa de aprovação humana sem retrabalho | > 60% | % de transições aprovadas na primeira tentativa |
| Taxa de auto-approve segura (sem reversão posterior) | > 90% | % de auto-approvals que o usuário não desfez depois |
| Código gerado que roda sem edição (via sandbox) | > 70% | % de execuções do Dev Agent que passam no sandbox sem correção manual |
| Custo médio por projeto | < $2 (revisado de <$1, que era subestimado) | Soma de tokens/custo de API por projeto |
| Uptime da plataforma | > 99% | UptimeRobot / status page |
| Retenção semanal | > 30% | % de usuários que criam ≥1 projeto/semana |

---

## 2. Requisitos Funcionais

### 2.1 Pipeline Kanban Visual (F-001)

**Critérios de Aceitação (ajustes vs v1.0):**
- [ ] Board com 6 colunas: Backlog, Researching, Planning, Reviewing, Production, Done
- [ ] Card exibe badge extra: "🤖 Auto-aprovado" quando aplicável, distinto de "✅ Aprovado por você"
- [ ] Demais critérios idênticos ao v1.0 (drag-and-drop, cores de status, modal de detalhes, responsivo)

**Estimativa:** 18 horas (+2h pela coluna extra e badge de auto-approve)

---

### 2.2 Ideation Agent (F-002)

Sem mudanças em relação ao v1.0.

**Estimativa:** 8 horas

---

### 2.3 Research Agent (F-003) — Novo no MVP

**User Story:** Como desenvolvedor solo, quero que minha ideia seja automaticamente confrontada com o mercado (concorrentes, discussões, gaps) e com código de referência reutilizável, sem eu precisar pesquisar manualmente.

**Arquitetura de integração:**
- Chama o **SRA** via seu servidor MCP (`mcp-server.mjs`) como cliente MCP; fallback para REST direto se MCP indisponível
- Query enviada ao SRA é montada a partir de `project_name` + `key_features` + `elevator_pitch` do Ideation Agent
- Recebe de volta o relatório Markdown de 8 seções do SRA (síntese, concorrentes, gaps, fontes)
- Dispara em paralelo o **Code Research Agent (F-008)** com os mesmos termos

**Critérios de Aceitação:**
- [ ] Timeout de 45s para resposta do SRA; se exceder, card segue com aviso "pesquisa de mercado incompleta" em vez de travar o pipeline
- [ ] Circuit breaker: se SRA falhar 3x seguidas, pipeline segue sem essa etapa e loga incidente
- [ ] Relatório do SRA salvo como Artifact (`type=markdown`, `agent_name=research_agent`)
- [ ] Cache: se a mesma ideia (ou muito similar) já foi pesquisada nos últimos 7 dias, reaproveita o resultado em vez de rechamar o SRA
- [ ] Tempo de execução: < 45s (dependente do SRA)
- [ ] Custo por execução: variável (depende de quantas fontes o SRA consulta); registrar e expor no dashboard

**Dependências:** F-002 (Ideation Agent) + SRA disponível na rede Docker

**Estimativa:** 10 horas (cliente MCP + fallback REST + cache + circuit breaker; a pesquisa em si já existe no SRA)

---

### 2.4 Code Research Agent — versão enxuta (F-008)

**User Story:** Como desenvolvedor solo, quero saber quais arquivos ou padrões de projetos de referência eu poderia reaproveitar, com aviso claro de licença, sem precisar vasculhar repositórios manualmente.

**Fluxo:**
1. Recebe lista de repositórios candidatos (dos resultados do SRA, filtrados por `similarity_score`/`relevance`)
2. Para cada repo candidato (top 2-3): busca `LICENSE`, `README.md` e estrutura de pastas via **GitHub API** (Contents API)
3. Se o README ou docs relevantes estiverem em site externo ao GitHub (ex: documentação própria do projeto), usa **Firecrawl** (`scrape`) para coletar esse conteúdo
4. Um único prompt de LLM recebe: README + estrutura de pastas + license + a ideia estruturada, e retorna: (a) lista de arquivos/padrões potencialmente reutilizáveis com justificativa, (b) classificação de licença (permissiva/copyleft/desconhecida) com aviso quando copyleft (ex: AGPL/GPL)
5. Resultado vira Artifact anexado ao card, disponível pro usuário importar manualmente pra Snippet Library

**Critérios de Aceitação:**
- [ ] Nunca baixa/copia código automaticamente para o projeto do usuário — apenas sugere e explica; importação é sempre manual (F-009)
- [ ] Todo repositório analisado tem campo de licença preenchido (`permissive` / `copyleft` / `unknown`) e aviso explícito se `copyleft`
- [ ] Uso de GitHub API para arquivos de código (não Firecrawl, por custo/velocidade); uso de Firecrawl apenas para conteúdo fora do domínio github.com
- [ ] Tempo de execução: < 60s
- [ ] Custo por execução: < $0.15

**Dependências:** F-003 (Research Agent, fornece candidatos)

**Estimativa:** 14 horas

---

### 2.5 Planner Agent (F-004)

Igual ao v1.0, com uma adição: o input agora inclui também o relatório do Research Agent e do Code Research Agent, não só o output do Ideation Agent.

**Critério adicional:**
- [ ] Stack recomendada leva em conta padrões identificados pelo Code Research Agent, quando existirem

**Estimativa:** 10 horas (sem mudança de esforço, só de input)

---

### 2.6 Reviewer Agent — versão leve (F-005) — Volta ao MVP

**User Story:** Como desenvolvedor solo, quero uma checagem automática de consistência entre a ideia original, a pesquisa e o plano antes de partir pra código, pra pegar contradições cedo.

**Critérios de Aceitação:**
- [ ] Input: Ideation + Research + Code Research + Planner outputs
- [ ] Output: lista de alertas de consistência (ex: "plano sugere stack X mas ideia original menciona restrição Y"), sem reescrever nada — só sinaliza
- [ ] Não bloqueia o pipeline: alertas aparecem no modal de aprovação do Planner, mas usuário decide se segue mesmo assim
- [ ] Tempo de execução: < 15s
- [ ] Custo por execução: < $0.05

**Dependências:** F-004 (Planner Agent)

**Estimativa:** 6 horas (1 prompt de validação, sem UI nova além do que já existe no modal de aprovação)

---

### 2.7 Dev Agent com Sandbox de Validação (F-006)

**User Story:** Como desenvolvedor solo, quero ter confiança de que o código entregue realmente roda, não só "parece certo".

**Adição vs v1.0:** após gerar o código, o Dev Agent tenta executá-lo num container efêmero isolado (`docker run --rm`, sem rede externa) antes de marcar como concluído.

**Critérios de Aceitação (adicionais aos do v1.0):**
- [ ] Código gerado é testado em container efêmero: instala dependências, roda build/lint básico
- [ ] Se falhar, Dev Agent recebe o stderr e tenta corrigir automaticamente (até 2 tentativas)
- [ ] Se ainda falhar após 2 tentativas, card vai pra "awaiting approval" com aviso explícito: "código pode não rodar sem ajustes — ver log de erro"
- [ ] Sandbox não tem acesso à rede externa nem a variáveis de ambiente sensíveis do host
- [ ] Tempo de execução: < 4 min (subiu de <2min do v1.0, pra acomodar o ciclo de validação/correção — meta mais realista)
- [ ] Custo por execução: < $1.20 (revisado de <$0.50, que estava subestimado)

**Dependências:** F-004 (Planner Agent) + F-005 (Reviewer Agent) + aprovação humana

**Estimativa:** 14 horas (código) + 8 horas (sandbox) = 22 horas

---

### 2.8 Human-in-the-Loop Gate com Auto-Approve (F-007)

Mantém tudo do v1.0 (aprovar/rejeitar/editar, timeout 24h, undo 5min), com uma adição:

**Critérios de Aceitação adicionais:**
- [ ] Se o `confidence_score` do agente (Ideation) for ≥ 0.85 **e** o Reviewer Agent não gerar nenhum alerta crítico, o card avança automaticamente sem esperar clique do usuário
- [ ] Toda transição auto-aprovada fica visualmente marcada e é reversível por até 30 min (janela maior que o undo manual, porque o usuário não teve chance de revisar em tempo real)
- [ ] Usuário pode desativar auto-approve globalmente nas configurações
- [ ] Dashboard mostra taxa de auto-approve e taxa de reversão (métrica de confiança no sistema)

**Estimativa:** 12 horas (v1.0) + 6 horas (lógica de auto-approve + janela de reversão estendida) = 18 horas

---

### 2.9 Snippet Library com Licença (F-009)

Igual ao v1.0, com um campo adicional obrigatório:

**Critério adicional:**
- [ ] Campo `license` (enum: `MIT`, `Apache-2.0`, `BSD`, `GPL`, `AGPL`, `unknown`, `proprietary`) obrigatório ao salvar snippet
- [ ] Se `license` for `GPL`/`AGPL`, exibir aviso visual (⚠️) na Snippet Library e no card onde foi usado

**Estimativa:** 8 horas (v1.0) + 2 horas (campo de licença + aviso visual) = 10 horas

---

### 2.10 Perfil de Preferências do Usuário (F-010) — Novo

**User Story:** Como desenvolvedor solo que usa a plataforma repetidamente, quero que o sistema aprenda meu estilo (framework de teste preferido, convenções de código) para que cada novo projeto já saia mais alinhado ao meu jeito de trabalhar, sem eu ter que repetir instruções.

**Como funciona:**
- Toda vez que o usuário **rejeita** ou **edita manualmente** um artefato do Planner ou Dev Agent, o sistema registra um par `(atributo, valor)` inferido da edição (ex: usuário trocou "Vitest" por "Jest" → `preferred_testing_framework: jest`)
- Esses pares são armazenados numa tabela `user_preferences`, com contador de confiança (quantas vezes essa preferência foi reforçada)
- Antes de rodar Planner/Dev Agent, o backend injeta as preferências com confiança ≥ 2 ocorrências no prompt como contexto ("o usuário historicamente prefere X")
- Preferências nunca são inferidas de um único evento isolado — só reforçadas por repetição, pra evitar ruído

**Critérios de Aceitação:**
- [ ] Tabela `user_preferences` populada automaticamente a partir de edições/rejeições
- [ ] Tela simples em Configurações mostrando preferências aprendidas, com opção de editar/remover manualmente
- [ ] Preferências aplicadas apenas com confiança ≥ 2 reforços (evita overfitting em 1 evento)
- [ ] Nenhuma preferência é aplicada de forma que contradiga uma instrução explícita do usuário no projeto atual

**Dependências:** F-004 (Planner Agent), F-006 (Dev Agent), F-007 (histórico de aprovação/rejeição)

**Estimativa:** 12 horas

---

### 2.11 Cap de Orçamento (F-011) — Novo

**User Story:** Como usuário, quero definir um limite de gasto mensal e por projeto para não ter surpresas de custo de API.

**Critérios de Aceitação:**
- [ ] Campo configurável: limite mensal (default $10) e limite por projeto (default $3)
- [ ] Ao atingir 80% do limite, notificação de aviso
- [ ] Ao atingir 100%, pipeline pausa novas execuções até o usuário aumentar o limite ou o mês virar
- [ ] Dashboard mostra gasto atual vs. limite em tempo real

**Dependências:** F-013 (Dashboard de Métricas, versão simplificada)

**Estimativa:** 8 horas

---

### 2.12 Onboarding Interativo (F-012) — Rebaixado para P1

Critérios idênticos ao v1.0, mas não bloqueia o lançamento do MVP — pode ser substituído por um guia em texto/vídeo curto na Fase 1 e implementado como tour interativo só na Fase 3.

**Estimativa:** 10 horas (mantida, só a prioridade muda)

---

### 2.13 Dashboard de Métricas (F-013) — Simplificado no MVP

**Versão simplificada pro MVP** (a versão completa do v1.0 vira v1.2):
- [ ] Cards de métricas essenciais: projetos criados, completados, custo total, gasto vs. limite (F-011)
- [ ] Tabela de execuções com status, tempo, custo, agente
- [ ] Sem gráficos de linha/pizza no MVP (adiados pra v1.2)

**Estimativa:** 4 horas (reduzida de 8h, versão simplificada)

---

## 3. Requisitos Não-Funcionais (ajustes)

### 3.1 Performance (revisado)

| Requisito | Target | Nota |
|-----------|--------|-----|
| Tempo de execução do Ideation Agent | < 15s | Sem mudança |
| Tempo de execução do Research Agent (SRA) | < 45s | Novo, dependente de serviço externo |
| Tempo de execução do Code Research Agent | < 60s | Novo |
| Tempo de execução do Reviewer Agent | < 15s | Novo |
| Tempo de execução do Planner Agent | < 30s | Sem mudança |
| Tempo de execução do Dev Agent (com sandbox) | < 4min | Revisado de <2min (v1.0 subestimava) |

### 3.2 Segurança (adição)

| Requisito | Implementação |
|-----------|--------------|
| Sandbox de execução de código gerado | Container efêmero sem rede externa, sem acesso a env vars sensíveis do host, `--rm` após execução |
| Comunicação entre serviços (AgentFlow ↔ SRA ↔ Firecrawl) | Rede Docker interna isolada; nenhum dos três serviços exposto publicamente no Docker Desktop |
| Checagem de licença | Obrigatória antes de qualquer sugestão de reuso de código de terceiros |

### 3.3 Escalabilidade

Sem mudanças relevantes vs. v1.0 — segue como single-tenant no MVP.

---

## 4. Arquitetura Técnica (revisada)

### 4.1 Diagrama de Alto Nível

```
┌───────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                  │
│  React 19 + Tailwind + Dnd-Kit + Zustand + TanStack Query         │
├───────────────────────────────────────────────────────────────────┤
│                         BACKEND (AgentFlow Studio)                 │
│  FastAPI + SQLAlchemy + Pydantic + SQLite                          │
│  Orquestra: Ideation, Research, Code Research, Planner,            │
│  Reviewer, Dev Agents                                              │
├───────────────────────────────────────────────────────────────────┤
│                         SANDBOX                                    │
│  Container efêmero (docker run --rm, sem rede) p/ validar código   │
├───────────────────────────────────────────────────────────────────┤
│         REDE DOCKER INTERNA (docker-compose network)              │
│  ┌─────────────────────┐        ┌──────────────────────────┐      │
│  │  Smart Research      │◄──────►│  Firecrawl (self-hosted) │      │
│  │  Agent (SRA)         │  usa   │  scrape/crawl/map        │      │
│  │  FastAPI+Celery+     │        │                          │      │
│  │  Redis+Neo4j+Chroma  │        │                          │      │
│  │  MCP server exposto  │        │  MCP/REST exposto        │      │
│  └─────────▲────────────┘        └──────────▲───────────────┘     │
│            │  MCP/REST                       │  REST (uso direto  │
│            │                                 │  pelo Code Research│
│            │                                 │  Agent, além do SRA│
└────────────┼─────────────────────────────────┼────────────────────┘
             │                                 │
   AgentFlow Studio backend consome ambos via cliente MCP (preferencial)
   ou REST (fallback), dentro da mesma rede Docker no Docker Desktop.

┌───────────────────────────────────────────────────────────────────┐
│                         EXTERNAL APIs                              │
│  GitHub API v3 (busca de repos + arquivos brutos de código)        │
│  Gemini 2.5 Pro (execução dos agentes de LLM)                      │
└───────────────────────────────────────────────────────────────────┘
```

**Nota de deploy:** no Docker Desktop, AgentFlow Studio, SRA e Firecrawl rodam como três `docker-compose` distintos na mesma rede Docker nomeada (`agentflow-net`), comunicando-se por nome de serviço (não por `localhost`). Isso já deixa o caminho pronto pra VPS: ao migrar, só é preciso recriar a rede e ajustar DNS interno — nenhuma mudança de código, já que os endpoints são configurados via variável de ambiente (`SRA_BASE_URL`, `FIRECRAWL_BASE_URL`), nunca hardcoded.

**Atenção a recursos:** rodar as três stacks simultaneamente no Docker Desktop (Neo4j + ChromaDB + Redis + Celery do SRA, mais o serviço do Firecrawl, mais o AgentFlow Studio) pode exigir 6-8GB de RAM alocada ao Docker Desktop. Vale confirmar isso antes de assumir esse setup como ambiente de dev padrão.

### 4.2 Stack Detalhada

Idêntica ao v1.0 (React 19, Tailwind, FastAPI, SQLite, Gemini 2.5 Pro), com adições:

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Cliente MCP | SDK oficial MCP (Python) | Consumir SRA e Firecrawl via protocolo MCP em vez de REST cru quando possível |
| Sandbox | Docker-in-Docker ou `docker run` a partir do host | Validação de código gerado sem acesso a rede/host |
| Cache de pesquisa | Tabela `research_cache` no SQLite (chave: hash da query) | Evita rechamar o SRA para ideias muito similares |

### 4.3 APIs e Integrações (revisado)

| Integração | Tipo | Uso | Observação |
|------------|------|-----|-----------|
| Smart Research Agent | MCP (preferencial) / REST | Pesquisa de mercado/concorrentes multi-fonte | Serviço próprio, container separado |
| Firecrawl (self-hosted) | MCP / REST | Scraping de conteúdo fora do GitHub | Serviço próprio, container separado; também usado internamente pelo SRA |
| GitHub API v3 | REST | Busca de repos + leitura de arquivos de código brutos | Preferir sobre Firecrawl para conteúdo dentro do github.com |
| Gemini API | REST | Execução de todos os agentes de LLM | Sem mudança |

### 4.4 Modelo de Dados (adições)

Mantém todas as entidades do v1.0 (User, Project, Card, Artifact, Execution, Snippet) e adiciona:

```
UserPreference
├── id: UUID (PK)
├── user_id: UUID (FK → User)
├── attribute: String (ex: "preferred_testing_framework")
├── value: String (ex: "jest")
├── confidence_count: Integer (quantas vezes foi reforçada)
├── last_reinforced_at: DateTime
├── created_at: DateTime
└── updated_at: DateTime

BudgetLimit
├── id: UUID (PK)
├── user_id: UUID (FK → User)
├── monthly_limit_usd: Float
├── per_project_limit_usd: Float
├── current_month_spend_usd: Float
├── updated_at: DateTime

ResearchCache
├── id: UUID (PK)
├── query_hash: String (unique)
├── source: Enum [sra, code_research]
├── result: Text (JSON/Markdown do relatório)
├── created_at: DateTime
└── expires_at: DateTime (7 dias)
```

Campo adicional em `Snippet`:
```
Snippet
├── ... (campos existentes do v1.0)
└── license: Enum [MIT, Apache-2.0, BSD, GPL, AGPL, unknown, proprietary]
```

---

## 5. Interface do Usuário (adições)

Mantém todas as telas do v1.0. Adições:

- **Modal de Aprovação (Tela 3):** nova tab "Pesquisa" mostrando o relatório do SRA e as sugestões do Code Research Agent (com avisos de licença destacados em vermelho quando `copyleft`)
- **Card no Kanban:** badge "🤖 Auto-aprovado" quando aplicável
- **Configurações:** nova seção "Preferências Aprendidas" (lista editável do que o sistema aprendeu) e "Limites de Orçamento"

---

## 6. Plano de Testes (adições)

| Módulo | Casos de Teste | Cobertura Mínima |
|--------|---------------|-----------------|
| Cliente MCP (SRA/Firecrawl) | Sucesso, timeout, circuit breaker após 3 falhas | 80% |
| Sandbox de validação | Código válido passa, código com erro é detectado e corrigido, falha após 2 tentativas é reportada | 85% |
| Perfil de Preferências | Preferência só é aplicada com confiança ≥2, não sobrepõe instrução explícita | 90% |
| Cap de Orçamento | Aviso em 80%, bloqueio em 100%, reset mensal | 90% |
| Checagem de Licença | Classificação correta MIT/GPL/AGPL/unknown a partir do arquivo LICENSE | 85% |

**Teste de integração adicional:** Research Agent → SRA indisponível → pipeline segue com aviso (não trava).

---

## 7. Cronograma (revisado)

| Fase | Semana | Entregável | Observação |
|------|--------|------------|-----------|
| Fase 0 | 1 | Validação manual do pipeline (3 ideias reais) + protocolo de comunicação | Sem mudança |
| Fase 1 | 2-5 | Core Platform: Kanban (6 colunas) + API + DB + Ideation Agent + integração MCP com SRA/Firecrawl | +1 semana vs v1.0 pela integração MCP |
| Fase 2 | 6-10 | Fleet de Agentes: Research, Code Research, Planner, Reviewer, Dev + Sandbox + Perfil de Preferências | +2 semanas vs v1.0 pelos agentes novos |
| Fase 3 | 11-13 | Polish: Onboarding, Dashboard simplificado, Cap de Orçamento, UX, Deploy | Ligeiramente reduzido (dashboard simplificado) |
| Fase 3.5 | 14-15 | GTM: Landing page + Product Hunt + Comunidade | Sem mudança |
| Beta | 16-17 | Beta launch + feedback + iteração | +1 semana |
| Launch | 18 | Lançamento público | Total: 18 semanas (vs 16 do v1.0) |

O cronograma cresceu 2 semanas em relação ao v1.0 pelas integrações novas (MCP, sandbox), mas isso substitui trabalho que teria sido gasto construindo pesquisa/busca do zero — o saldo líquido de esforço é provavelmente positivo, já que SRA e Firecrawl já existem.

---

## 8. Apêndices

### 8.1 Novos ADRs

#### ADR-005: Research Agent delega ao Smart Research Agent externo em vez de implementar busca própria

**Contexto:** O SRA já existe, com pipeline de pesquisa multi-fonte mais sofisticado do que o planejado internamente (F-006 do v1.0).

**Decisão:** Research Agent do AgentFlow Studio consome o SRA via MCP (fallback REST), em vez de reimplementar busca de mercado.

**Consequências:**
- Positivas: reuso de infraestrutura madura, menos trabalho de engenharia, qualidade superior (multi-fonte, ranking, gap detection)
- Negativas: dependência de serviço externo — precisa de circuit breaker e degradação graciosa; acoplamento de deploy (dois serviços a manter)

**Reversível em:** Sempre — a interface é um cliente MCP/REST; trocar de fonte de pesquisa não exige mudança de schema.

---

#### ADR-006: Uso do Firecrawl self-hosted para coleta web fora do GitHub

**Contexto:** Firecrawl (AGPL-3.0 no core) já está sendo hospedado pelo usuário e usado pelo SRA internamente.

**Decisão:** Code Research Agent usa GitHub API para conteúdo dentro do github.com (mais rápido/barato) e Firecrawl apenas para fontes externas (docs, blogs).

**Consequências:**
- Positivas: evita overhead desnecessário de scraping pra conteúdo já disponível via API nativa; aproveita infraestrutura já madura para o resto
- Negativas: licença AGPL do Firecrawl exige atenção — uso interno como ferramenta de suporte é seguro, mas se o AgentFlow Studio algum dia oferecer o Firecrawl modificado como serviço de rede para terceiros, a AGPL exigiria disponibilizar o código-fonte modificado

**Reversível em:** Sim — troca de ferramenta de scraping não afeta o schema de dados.

---

#### ADR-007: Auto-approve condicionado a confidence score + ausência de alertas do Reviewer

**Contexto:** Meta de <45min ideia→código só é atingível se nem toda transição exigir espera por decisão humana.

**Decisão:** Transições com `confidence_score ≥ 0.85` e nenhum alerta crítico do Reviewer avançam automaticamente, com janela de reversão de 30 min.

**Consequências:**
- Positivas: viabiliza a meta de tempo total para casos simples, sem abrir mão de segurança pros casos complexos
- Negativas: risco de o usuário não perceber um erro sutil a tempo; mitigado pela janela de reversão e por métricas de "taxa de reversão" monitoradas de perto no beta

**Reversível em:** Usuário pode desativar globalmente a qualquer momento.

### 8.2 Glossário (adições ao v1.0)

| Termo | Definição |
|-------|-----------|
| SRA | Smart Research Agent — ferramenta própria de pesquisa multi-fonte, consumida via MCP |
| MCP | Model Context Protocol — protocolo padrão para agentes/ferramentas de IA se comunicarem |
| Auto-approve | Transição de fase aprovada automaticamente pelo sistema, sem clique do usuário, baseada em confidence score |
| Confidence Count | Número de vezes que uma preferência do usuário foi reforçada antes de ser aplicada automaticamente |

### 8.3 Referências (adições)

- Smart Research Agent: https://github.com/CarlosFrazao/smart-research-agent
- Firecrawl (self-hosted): https://github.com/CarlosFrazao/firecrawl
- Model Context Protocol: https://modelcontextprotocol.io

---

## 9. Checklist de Aprovação do PRD

| # | Item | Status |
|---|------|--------|
| 1 | Todos os requisitos funcionais têm critérios de aceitação testáveis | ✅ |
| 2 | Integrações externas (SRA, Firecrawl) têm estratégia de fallback documentada | ✅ |
| 3 | Métricas de tempo não são mais contraditórias entre si | ✅ |
| 4 | Custos por execução recalibrados com margem realista | ✅ |
| 5 | Checagem de licença obrigatória para reuso de código de terceiros | ✅ |
| 6 | ADRs documentando as novas decisões de arquitetura | ✅ |
| 7 | Cronograma ajustado refletindo o esforço real das novas integrações | ✅ |
| 8 | Personalização (Perfil de Preferências) com salvaguardas contra overfitting em evento único | ✅ |

---

**Documento revisado por:** Claude (Sonnet), a pedido do usuário
**Data:** 2026-07-10
**Versão:** 1.1
**Status:** Aguardando aprovação do usuário antes de seguir para atualização do Kanban de Produção
