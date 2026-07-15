# Instruções Iniciais de Execução — AgentFlow Studio v1.1

> **Destinatário:** Claude (CLI / Claude Code)
> **Objetivo:** Iniciar e planejar o MVP do AgentFlow Studio a partir do zero.
> **Instruções Invioláveis:** Siga as regras de carregamento atômico de skills sob demanda antes de codificar.

---

## 🤖 1. Modelo de IA Recomendado para Iniciar
Para a **Fase 1 (Planejamento, Design de APIs e Modelagem)**, o modelo mais recomendado no seu `settings.json` é:
* **`tencent/hy3:free` (Tencent Hy3)**
* **Por quê:** O Hy3 tem a melhor capacidade de raciocínio conceitual e lógica abstrata (MoE 295B com CoT). Ele lerá o PRD, a Spec Técnica e estruturará o banco de dados sem alucinar ou misturar arquivos de forma bagunçada.
* **Nota:** Quando começar a **escrever código e testes nas Fases 2 a 5**, você pode alternar para o **`qwen/qwen3-coder:free`** ou **`cohere/north-mini-code:free`** pela rapidez de resposta e escrita cirúrgica de funções.

---

## 📋 2. Roteiro Passo a Passo de Inicialização do Projeto

Claude, execute as etapas abaixo na ordem exata:

### Passo 1: Boot e Leitura das Especificações
1. Leia o arquivo [PRD_AgentFlow_Studio_v1_1.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Cria/PRD_AgentFlow_Studio_v1_1.md) inteiro para entender o escopo do board Kanban e dos agentes.
2. Leia a [Spec_Tecnica_Integracao_v1_0.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/Cria/Spec_Tecnica_Integracao_v1_0.md) para entender como o AgentFlow Studio se comunicará com a API do SRA (porta 3458) e do Firecrawl (porta 3002) usando a rede do Docker.
3. Leia o arquivo de governança [CLAUDE.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/CLAUDE.md) na raiz do projeto.

### Passo 2: Executar a Fase 1 (Planejamento e Setup)
1. **Modelagem do Banco de Dados (SQLite):** Planeje a tabela de `projects` (cards do Kanban), `executions` (logs de execução de agentes), `user_preferences` (preferências de stack do usuário) e `budget_caps` (orçamentos).
2. **Divisão de Pastas:** Crie a estrutura de diretórios inicial do projeto:
   * `backend/` (código FastAPI, banco SQLite, orquestradores de agentes).
   * `frontend/` (painel web do Kanban, métricas e sidebar).
   * `sandbox/` (ambiente isolado onde o Dev Agent validará se o código gerado roda).
3. **Criação do Plano de Implementação:** Escreva o plano inicial de desenvolvimento no arquivo `.claude/plans/fase1-planejamento.md` antes de criar códigos físicos.

---

## 🧠 3. Habilidades (Skills) Obrigatórias Mapeadas no Workspace

Para evitar desperdício de tokens de contexto, você deve ler a skill correspondente **apenas no momento em que for iniciar a respectiva tarefa**.

Aqui estão as skills de engenharia copiadas para o seu diretório portátil de configurações e os caminhos físicos exatos para leitura:

### 1. Modelagem de APIs e Rotas
* **Skill:** `api-patterns`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/api-patterns/SKILL.md)
* **Quando carregar:** Ao estruturar as rotas HTTP de transições de cartões do Kanban e integrações FastAPI.

### 2. Desenvolvimento em Python
* **Skill:** `python-pro`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/python-pro/SKILL.md)
* **Quando carregar:** Ao escrever toda a lógica Python dos agentes do pipeline e backend FastAPI.

### 3. Requisições e Integrações de Rede
* **Skill:** `http-request-mastery`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/http-request-mastery/SKILL.md)
* **Quando carregar:** Ao programar a integração HTTP assíncrona com os endpoints do SRA (`http://localhost:3458`) e do Firecrawl (`http://localhost:3002`).

### 4. Orquestração Multi-Agentes
* **Skill:** `multi-agent-patterns`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/multi-agent-patterns/SKILL.md)
* **Quando carregar:** Ao programar a lógica de loop que passa a ideia do cartão de um agente para outro (Ideation → Research → Planner → Reviewer → Dev).

### 5. Interface Gráfica Reativa
* **Skill:** `ui-ux-pro-max`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/ui-ux-pro-max/SKILL.md)
* **Quando carregar:** Ao criar e polir a interface visual do board Kanban e os modais de aprovação humana (HITL).

### 6. Configurações de Sandbox e Docker
* **Skill:** `docker-expert`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/docker-expert/SKILL.md)
* **Quando carregar:** Ao configurar o compose do AgentFlow na rede externa `firecrawl_backend` e a sandbox Docker para validação de código.

### 7. Escrever Testes Unitários e E2E
* **Skill:** `test-driven-development`
* **Caminho de Leitura:** [SKILL.md](file:///F:/Criando%20sites%20pelo%20pc/Site%20AgentFlow%20Studio/.claude/skills/test-driven-development/SKILL.md)
* **Quando carregar:** Ao escrever testes unitários para os endpoints e simulações do Playwright para o Kanban.

---

## 🚀 Prompt Otimizado de Um Clique para Inicialização:
```text
Siga o Protocolo de Inicialização e a missão em CLAUDE.md. Leia a documentação em Cria/PRD_AgentFlow_Studio_v1_1.md e Cria/Spec_Tecnica_Integracao_v1_0.md. Em seguida, leia de forma atômica a skill em .claude/skills/api-patterns/SKILL.md para planejar a arquitetura base do MVP e os diretórios do projeto.
```
