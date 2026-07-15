# AgentFlow Studio

Plataforma de orquestração multi-agente visual baseada em board Kanban que
automatiza o pipeline de criação de produtos digitais
(Ideia → Pesquisa → Plano → Revisão → Código → Deploy) com aprovação
humana (HITL) e agentes especialistas.

## Stack

- **Backend:** Python 3.12 + FastAPI (API REST versionada em `/api/v1`)
- **Banco:** SQLite (SQLAlchemy 2.x async) — `backend/data/agentflow.db`
- **Frontend:** React + Vite + Tailwind (build em `frontend/dist/`)
- **Orquestração:** padrão Supervisor (máquina de estados no `orchestrator.py`)
- **Agentes:** Ideation, Research, Planner, Reviewer, Dev (com sandbox)
- **Event Bus:** pub/sub em memória (`asyncio.Queue`) para desacoplar agentes

## Estrutura

```
backend/
  app/
    api/v1/        # routers (cards, projects, agents, run, dashboard...)
    core/          # config, database, security, responses, exceptions
    models/        # SQLalchemy ORM (Card, Project, Agent, ...)
    schemas/       # Pydantic (request/response)
    services/      # orchestrator, agents, event_bus, prompt_hydration
  tests/           # suíte pytest (TDD)
frontend/          # React + Vite (Kanban + Dashboard)
docker-compose.yml
```

## Pré-requisitos

- Python 3.12+
- (Opcional) Docker + Docker Compose para subir tudo junto

## Como rodar o backend (dev)

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

A API fica em `http://localhost:8000/api/v1` e o frontend (build de produção)
é servido em `http://localhost:8000/` pela mesma origem.

### Autenticação

A API é protegida por JWT. Registre um usuário e use o token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"voce@example.com","password":"sua-senha","display_name":"Voce"}'
# Use o access_token retornado no header: Authorization: Bearer <token>
```

## Como rodar os testes

```bash
cd backend
pytest                      # suíte completa
pytest --cov=app            # com cobertura
pytest tests/test_event_bus.py   # teste específico
```

## Como subir com Docker

```bash
docker compose up --build
```

Isso sobe o backend (FastAPI + SQLite) e o frontend (Nginx) na mesma rede.
Veja `docker-compose.yml` para portas e variáveis de ambiente.

## Variáveis de ambiente (.env)

Copie e ajuste conforme necessário:

```
GEMINI_API_KEY=...           # chave do LLM dos agentes
DEMO_MODE=false              # true = avança cards sem chamar LLM real
JWT_SECRET=...               # obrigatório em produção
SRA_MCP_URL=http://sra-app:3458/mcp/sse
FIRECRAWL_MCP_URL=http://firecrawl-api-new:3002/mcp/sse
```

## Pipeline Kanban (colunas)

`backlog → researching → planning → reviewing → production → done`

O endpoint `POST /api/v1/cards/{id}/run` executa o agente da coluna atual,
persiste o Artifact/Execution e avança o card. O Reviewer realiza o ciclo
Criação↔Revisão: se a revisão falha, o card volta para `production` com
os logs anexados em `meta.review_logs`.

## Features implementadas (além do MVP)

- **Definição declarativa de agentes** (`POST /api/v1/agents`): cria agentes
  persistidos no SQLite e espelhados em YAML em `.claude/skills/`.
- **Prompt Hydration:** ao criar um card, o título em PT informal é traduzido
  para EN técnico e enriquecido com as regras de governance (em `meta.hydrated_prompt`).
- **Event Bus** desacoplado para comunicação entre agentes.
