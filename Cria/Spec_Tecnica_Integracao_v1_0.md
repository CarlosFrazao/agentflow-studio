# Especificação Técnica de Integração

## AgentFlow Studio ↔ Smart Research Agent ↔ Firecrawl

**Versão:** 1.0
**Data:** 2026-07-10
**Status:** Rascunho técnico — baseado em investigação direta dos dois repositórios
**Complementa:** PRD_AgentFlow_Studio_v1_1.md

---

## 0. Como usar este documento

Este documento existe para fechar a lacuna que o PRD deixou em aberto: ele não inventa endpoints nem formatos de dado — cada informação abaixo está marcada como **✅ Confirmado** (visto diretamente no código/README/compose dos repositórios) ou **⚠️ A confirmar** (inferido, precisa validar rodando o serviço localmente e olhando o Swagger em `/docs`). Isso é importante: eu investiguei o README, o `docker-compose.yml`, o `.env.example` e o `mcp-server.mjs` do SRA, e o README do Firecrawl — mas **não tive acesso ao arquivo real de rotas da API** (`api/main.py` ou equivalente, bloqueado por robots.txt do GitHub para listagem de diretório). Onde isso importa, deixei explícito.

---

## 1. Smart Research Agent (SRA) — Ficha Técnica

### 1.1 O que é (✅ confirmado)

SRA v6.0, ecossistema de pesquisa multi-fonte (GitHub, HN, Reddit, ArXiv, ProductHunt, web via Firecrawl/Jina), licença **MIT**. Pipeline: Intent Analyzer → Query Expander → Source Planner → busca paralela → Quality Ranker → Gap Detector → Synthesizer → Report Generator (Markdown, 8 seções).

### 1.2 Como sobe (✅ confirmado)

```bash
# API REST (porta 3458, com Swagger automático)
uvicorn api.main:app --port 3458 --reload
# Docs: http://localhost:3458/docs

# Worker assíncrono (opcional, para filas)
celery -A src.worker.celery_app worker --loglevel=info

# Via Docker Compose (recomendado)
docker compose up -d                          # só o SRA, standalone
docker compose --profile dev up -d            # SRA + SearXNG
docker compose --profile firecrawl up -d      # SRA + Firecrawl embutido no próprio compose do SRA
docker compose --profile full up -d           # tudo (Redis, ChromaDB, Neo4j legado, Firecrawl, SearXNG)
```

**Ponto importante que muda uma suposição do PRD v1.1:** o SRA foi migrado na v6.2.0 de Neo4j para **KuzuDB embutido** (arquivo local em `./kuzu_data/`, sem container separado). O serviço `neo4j` que ainda aparece no `docker-compose.yml` é mantido só por compatibilidade histórica e pode ser ignorado. Isso significa que **o SRA não exige tanta RAM quanto eu tinha estimado antes** — ele roda "sozinho" (sem nenhum perfil) com fallback automático para clientes em memória quando Redis/ChromaDB/Firecrawl não estão presentes. Meu aviso anterior sobre 6-8GB de RAM no Docker Desktop era conservador demais; na configuração mínima, o SRA sozinho deve rodar confortavelmente com muito menos.

### 1.3 Endpoints e portas (✅ confirmado onde indicado)

| Porta | Serviço | Endpoint | Status |
|---|---|---|---|
| 3458 | API REST (FastAPI) | Base | ✅ confirmado |
| 3458 | Swagger UI | `/docs` | ✅ confirmado |
| 3458 | Health check | `/health` | ✅ confirmado (usado no healthcheck do compose) |
| 3458 | MCP (SSE) | `/mcp/sse` | ✅ confirmado (visto em `mcp-server.mjs`) |
| 3458 | Pesquisa | `/api/research*` (rota exata não confirmada) | ⚠️ a confirmar no `/docs` |
| 8001 | Prometheus | `/metrics` | ✅ confirmado |
| 8501 | Streamlit UI | — | ✅ confirmado |

**Ação recomendada:** antes de escrever o código do Research Agent, suba o SRA localmente e abra `http://localhost:3458/docs` — lá está o contrato exato (nomes de campos, schema de request/response) dos endpoints de pesquisa. Meu palpite (baseado no padrão do resto do projeto e no comentário do `.env.example` sobre `/api/research*`) é algo como `POST /api/research` recebendo `{"query": "...", "mode": "guerrilha"|"cirurgia"}`, mas isso **precisa ser validado**, não implementado às cegas.

### 1.4 Autenticação e CORS (✅ confirmado)

```
SRA_API_KEY=          # vazio = autenticação desabilitada (uso local/dev)
CORS_ALLOWED_ORIGINS=*  # em produção, restringir às origens reais
```

Quando `SRA_API_KEY` está definida, os endpoints `/api/research*` exigem o header `X-API-Key: <valor>`. Para o setup local no Docker Desktop, deixar em branco é aceitável; ao migrar para VPS, gerar uma chave (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) e configurá-la nos dois lados.

### 1.5 Modos de pesquisa (✅ confirmado que existem, ⚠️ semântica exata a confirmar)

A CLI expõe dois modos: `--mode guerrilha` e `--mode cirurgia`. Pelo nome e pelo padrão comum em ferramentas assim, minha leitura é: **guerrilha** = busca rápida/rasa (poucas fontes, resposta em segundos, mais barata) e **cirurgia** = busca profunda/precisa (mais fontes, mais iterações, mais cara e lenta). Isso bate com `MAX_ITERATIONS=2` no `.env.example` — provavelmente controla quantas rodadas de gap-detection→nova busca cada modo permite. **Vale confirmar com um teste real** (`python cli/main.py search "teste" --mode guerrilha` vs `--mode cirurgia`, comparando tempo e tamanho do relatório) antes de fixar isso no código do Research Agent do AgentFlow.

**Recomendação de uso:** Research Agent do AgentFlow chama em modo `guerrilha` por padrão (compatível com a meta de tempo do pipeline); oferece um botão "pesquisa aprofundada" no modal de aprovação que rechama em modo `cirurgia` sob demanda.

### 1.6 Variáveis de ambiente relevantes para a integração (✅ confirmado)

```
LLM_PROVIDER=gemini              # já alinhado com o resto do AgentFlow Studio
GITHUB_TOKEN=<seu_pat>           # necessário para o GitHub Searcher não ser rate-limited
FIRECRAWL_API_KEY=local_bypass   # placeholder aceito por instância self-hosted
FIRECRAWL_BASE_URL=http://firecrawl:3002   # dentro da rede Docker (nome do serviço)
MAX_RESULTS_PER_SOURCE=15
MAX_ITERATIONS=2
TIMEOUT_PER_SOURCE=30            # 30s por fonte × múltiplas fontes em paralelo
```

**Correção importante ao PRD v1.1:** eu tinha recomendado timeout de 45s no Research Agent do AgentFlow para chamar o SRA. Com `TIMEOUT_PER_SOURCE=30s`, mesmo com busca paralela, picos de latência (retry, fonte lenta) podem levar a resposta total a passar de 45s facilmente. **Ajustar o timeout do lado do AgentFlow para 90s**, com o card mostrando "pesquisando..." nesse intervalo.

### 1.7 Topologia de rede (✅ confirmado, corrige o ADR-005 do PRD v1.1)

O `docker-compose.yml` do SRA declara:

```yaml
networks:
  default:
    name: smart-research-agent_default
  firecrawl_net:
    external: true
    name: firecrawl_backend
```

Ou seja: **o SRA espera que uma rede externa chamada `firecrawl_backend` já exista**, criada pelo próprio stack do Firecrawl. Isso muda a recomendação do PRD v1.1: em vez de o AgentFlow Studio criar sua própria rede `agentflow-net` e esperar que SRA/Firecrawl se juntem a ela, **o caminho natural é o inverso — o AgentFlow Studio deve se juntar à rede externa `firecrawl_backend` que o Firecrawl já cria**, já que essa é a rede que o SRA já foi desenhado para usar. Ver seção 4 para o `docker-compose.yml` corrigido.

---

## 2. Firecrawl (self-hosted) — Ficha Técnica

### 2.1 O que é (✅ confirmado)

Fork de `mendableai/firecrawl` (o projeto Firecrawl real), com adições próprias (`firecrawl-cli-skills`, `searxng`). Núcleo licenciado **AGPL-3.0**; SDKs e alguns componentes de UI em **MIT**.

### 2.2 Endpoints (✅ confirmado, API v2)

| Endpoint | Método | Uso no Code Research Agent |
|---|---|---|
| `/v2/scrape` | POST | Coletar conteúdo de 1 página (docs, blog) → markdown limpo |
| `/v2/crawl` | POST | Coletar um site inteiro (assíncrono, retorna job ID) |
| `/v2/map` | POST | Descobrir todas as URLs de um site rapidamente |
| `/v2/search` | POST | Buscar na web e já trazer conteúdo das páginas |
| `/v2/agent` | POST | Descrever o que precisa em linguagem natural, sem saber a URL de antemão; aceita `schema` Pydantic para saída estruturada |
| `/v2/batch/scrape` | POST | Múltiplas URLs de uma vez |

Exemplo real de chamada (adaptado do README, self-hosted usa `http://localhost:3002` em vez de `https://api.firecrawl.dev`):

```bash
curl -X POST 'http://firecrawl:3002/v2/scrape' \
  -H 'Authorization: Bearer local_bypass' \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://exemplo-de-docs.dev/getting-started"}'
```

### 2.3 Porta — atenção a uma inconsistência (⚠️ a confirmar)

O `docker-compose.yml` do **SRA** aponta o default de `FIRECRAWL_BASE_URL` para `http://firecrawl:3002` (dentro da rede Docker). Já o `.env.example` do SRA, pensado para rodar **fora** do Docker (dev local), usa `http://localhost:3022`. Essa diferença de porta (3002 vs 3022) provavelmente é só remapeamento de porta do host vs porta interna do container — mas **vale confirmar olhando o `docker-compose.yaml` do próprio repositório Firecrawl** antes de fixar isso na configuração do AgentFlow Studio, para não gastar tempo debugando uma conexão recusada por causa de uma porta trocada.

### 2.4 Nota legal sobre a licença (✅ confirmado — relevante para o seu caso)

O núcleo é **AGPL-3.0**. Isso significa: usar o Firecrawl internamente (como o AgentFlow Studio vai fazer, chamando a API de dentro da sua própria infraestrutura) **não** aciona nenhuma obrigação de abrir código — a AGPL só exige disponibilizar o código-fonte modificado se você **oferecer o serviço modificado para terceiros pela rede**. Como o Firecrawl aqui é infraestrutura interna (não um produto que você revende), está tudo certo. Isso só viraria um problema se, no futuro, o AgentFlow Studio decidisse expor a API do Firecrawl modificada diretamente para clientes externos como parte da oferta paga — nesse caso, precisaria reavaliar.

### 2.5 Uso recomendado no Code Research Agent

Reforçando o que já foi discutido: usar **GitHub API** para arquivos de código dentro do github.com (mais rápido, mais barato, já tem `GITHUB_TOKEN`), e reservar o Firecrawl para o que está **fora** do GitHub (`/v2/scrape` para uma página de docs específica, `/v2/agent` quando não se sabe a URL exata e é mais fácil descrever o que se quer, ex: *"encontre a página de arquitetura deste projeto e resuma os componentes principais"*).

---

## 3. Cliente de Integração — Esqueleto de Referência

Pseudocódigo Python/FastAPI para o cliente que o AgentFlow Studio deve implementar. **Decisão importante que corrige o ADR-005 do PRD v1.1:** para chamadas backend-a-backend (AgentFlow → SRA / AgentFlow → Firecrawl), **use REST direto, não MCP**. O `mcp-server.mjs` do SRA é uma ponte STDIO↔SSE pensada para conectar **IDEs/agentes de código interativos** (Claude Code, Cursor) ao SRA — não faz sentido para um serviço backend chamar outro serviço backend. MCP continua fazendo sentido se, no futuro, você quiser que o *próprio* AgentFlow Studio seja consumido como ferramenta por um assistente de código externo — mas para a orquestração interna do pipeline, REST simples é mais robusto (sem sessão SSE para gerenciar, sem reconexão, sem lógica de buffer).

```python
# clients/sra_client.py
import httpx
from typing import Literal

class SRAClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.timeout = timeout

    async def research(
        self, query: str, mode: Literal["guerrilha", "cirurgia"] = "guerrilha"
    ) -> dict:
        """
        Chama o SRA para pesquisa de mercado/concorrentes.
        ATENÇÃO: endpoint exato (/api/research vs outro) e formato de payload
        precisam ser confirmados em http://localhost:3458/docs antes de
        usar isso em produção — o abaixo é a melhor inferência disponível.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/research",
                    json={"query": query, "mode": mode},
                    headers=self.headers,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException:
                raise SRAUnavailableError("timeout")
            except httpx.HTTPStatusError as e:
                raise SRAUnavailableError(f"http_{e.response.status_code}")

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
            except httpx.RequestError:
                return False


class SRAUnavailableError(Exception):
    pass
```

```python
# clients/firecrawl_client.py
import httpx

class FirecrawlClient:
    def __init__(self, base_url: str, api_key: str = "local_bypass", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.timeout = timeout

    async def scrape(self, url: str) -> dict:
        """Coleta uma página específica em markdown limpo."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v2/scrape",
                json={"url": url},
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def agent(self, prompt: str, urls: list[str] | None = None, schema: dict | None = None) -> dict:
        """Coleta guiada por linguagem natural, sem precisar saber a URL exata."""
        payload = {"prompt": prompt}
        if urls:
            payload["urls"] = urls
        if schema:
            payload["schema"] = schema
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/v2/agent", json=payload, headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()
```

**Circuit breaker simples (aplicar aos dois clientes):**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_after_seconds: int = 60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_after = reset_after_seconds
        self.open_until: float | None = None

    def is_open(self) -> bool:
        import time
        if self.open_until and time.time() < self.open_until:
            return True
        if self.open_until:  # janela passou, reseta
            self.failures = 0
            self.open_until = None
        return False

    def record_failure(self):
        import time
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.reset_after

    def record_success(self):
        self.failures = 0
        self.open_until = None
```

---

## 4. Topologia de Rede Docker — `docker-compose.yml` de Referência

Assumindo que o Firecrawl (repositório próprio) sobe primeiro e cria a rede externa `firecrawl_backend` (⚠️ confirmar o nome exato no `docker-compose.yaml` do repositório Firecrawl antes de aplicar):

```yaml
# docker-compose.yml do AgentFlow Studio
services:
  agentflow-backend:
    build: .
    container_name: agentflow-backend
    env_file: .env
    ports:
      - "8000:8000"
    networks:
      - default
      - firecrawl_backend   # mesma rede externa que o SRA já usa
    environment:
      - SRA_BASE_URL=http://sra-app:3458
      - FIRECRAWL_BASE_URL=http://firecrawl:3002
    depends_on: []   # propositalmente vazio — ver seção 5 sobre não travar o boot

  agentflow-frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    networks:
      - default

networks:
  default:
    name: agentflow-studio_default
  firecrawl_backend:
    external: true
```

**Ordem de subida recomendada no Docker Desktop:**
```bash
# 1. Sobe o Firecrawl primeiro (cria a rede externa)
cd firecrawl && docker compose up -d

# 2. Sobe o SRA (se junta à rede externa)
cd ../smart-research-agent && docker compose --profile firecrawl up -d

# 3. Sobe o AgentFlow Studio (se junta à mesma rede externa)
cd ../agentflow-studio && docker compose up -d
```

---

## 5. Circuit Breaker e Degradação Graciosa — Comportamento Esperado

| Cenário | Comportamento do AgentFlow Studio |
|---|---|
| SRA fora do ar ao subir o AgentFlow | Backend sobe normalmente (sem `depends_on` bloqueante); Research Agent fica marcado como indisponível até o próximo health check passar |
| SRA cai durante uma pesquisa em andamento | Timeout de 90s → card recebe aviso "pesquisa de mercado incompleta" → pipeline segue para o Planner sem esse insumo |
| SRA falha 3x seguidas | Circuit breaker abre por 60s → chamadas seguintes falham rápido (sem esperar timeout) até a janela passar |
| Firecrawl fora do ar | Code Research Agent usa só GitHub API (README/estrutura), sem enriquecer com fontes externas; card informa "análise de código limitada à API do GitHub" |

---

## 6. O Que Ainda Falta Confirmar (checklist antes de codar)

- [ ] Endpoint exato de pesquisa do SRA (`/api/research` ou outro nome) — checar em `http://localhost:3458/docs` após subir o serviço
- [ ] Formato exato do payload de request e response do endpoint de pesquisa (nomes de campos)
- [ ] Semântica exata de `--mode guerrilha` vs `--mode cirurgia` (tempo/custo/profundidade de cada um)
- [ ] Nome exato da rede externa criada pelo `docker-compose.yaml` do repositório Firecrawl (`firecrawl_backend` é o nome que o SRA espera — confirmar que bate)
- [ ] Porta real do Firecrawl self-hosted (3002 vs 3022 — provavelmente host vs container, mas confirmar)
- [ ] Se o Celery/Redis do SRA é necessário para o modo de uso do AgentFlow (chamada síncrona simples) ou só para processamento em lote/assíncrono pela CLI

---

## 7. Próximo Passo Sugerido

Com este documento, o PRD v1.1 e o Kanban interativo, você já tem: o quê construir, em que ordem, e como as peças se conectam tecnicamente — com toda suposição não verificada marcada explicitamente. O próximo passo de maior valor antes de começar a Fase 1 é rodar os dois serviços (SRA e Firecrawl) localmente por 15-20 minutos só para abrir o Swagger do SRA e confirmar os itens da checklist da seção 6 — isso elimina a maior fonte restante de erro de implementação a um custo baixíssimo.
