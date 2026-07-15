# Prompts de Execução — Para a IA de Código

## AgentFlow Studio — Guia de Uso dos Documentos

**Versão:** 1.0
**Data:** 2026-07-10
**Para usar com:** Claude Code, Cursor, ou qualquer IA de código com acesso a arquivos

---

## 0. Como usar este arquivo

Cada seção abaixo é **um prompt pronto pra copiar e colar** na sua IA de código, na ordem em que aparecem. Regras de uso:

1. **Não pule etapas.** Cada prompt assume que o anterior já foi testado e está funcionando. Se você mandar o Prompt 3 antes de validar o Prompt 1, o erro de um vira erro escondido no outro.
2. **Antes de cada prompt, anexe os 4 documentos** (`PRD_AgentFlow_Studio_v1_1.md`, `Kanban_AgentFlow_Studio_v1_0.md`, `Spec_Tecnica_Integracao_v1_0.md`, `Prompts_Agentes_AgentFlow_v0_1.md`) na conversa com a IA de código — todos os prompts abaixo pressupõem que ela pode consultá-los.
3. **Todo prompt termina com uma seção "Antes de começar" e uma "Definição de pronto".** Não deixe a IA pular direto pra "Definição de pronto" — a seção "Antes de começar" existe justamente pra forçar uma pausa em pontos onde inventar é mais provável que acontecer.
4. Depois de cada prompt, rode você mesmo o que foi entregue antes de colar o próximo. Isso é o que transforma "a IA disse que funcionou" em "eu vi que funciona".

---

## PROMPT 0 — Validação Manual da Fase 0 (sem código)

**Quando usar:** primeiro de todos, antes de escrever qualquer linha de código. Pode ser rodado numa conversa de chat normal, não precisa ser numa IA de código com acesso a arquivos.

```
Você vai me ajudar a validar manualmente os 6 agentes do AgentFlow Studio antes
de eu escrever qualquer código. Tenho um documento chamado
"Prompts_Agentes_AgentFlow_v0_1.md" com o prompt, o schema de input/output e
um exemplo esperado de cada agente (Ideation, Research, Code Research,
Planner, Reviewer, Dev).

Vou te dar 3 ideias de produto reais (uma simples, uma média, uma complexa).
Para cada uma das 3 ideias, quero que você:

1. Rode o prompt do Ideation Agent com a ideia bruta, mostrando a saída JSON.
2. Use a saída do Ideation como input do Research Agent (só a parte de gerar
   a query — não tem como você chamar o SRA de verdade nesta conversa, então
   apenas gere a query e o modo, e finja um "market_summary" plausível pra
   seguirmos o teste).
3. Continue a cadeia: Code Research (com um repositório fictício mas
   plausível) → Planner → Reviewer → Dev Agent (gere só a camada backend).
4. Ao final de cada agente, me diga: a saída ficou boa? Faltou algum campo?
   O agente inventou alguma coisa que não estava no input? O confidence_score
   fez sentido?

No final das 3 ideias, me dê um resumo: quais dos 6 prompts precisam de
ajuste antes de eu formalizar isso no código, e por quê.

Primeira ideia: [DESCREVA AQUI A PRIMEIRA IDEIA]
```

**Antes de começar:** troque `[DESCREVA AQUI A PRIMEIRA IDEIA]` pelas suas 3 ideias reais (rode uma de cada vez, ou peça pra IA fazer as 3 na mesma resposta se preferir).

**Definição de pronto:** você tem uma lista clara de quais dos 6 prompts do documento precisam de ajuste, e já ajustou o `Prompts_Agentes_AgentFlow_v0_1.md` antes de seguir pro Prompt 1.

---

## PROMPT 1 — Fase 1a: Infraestrutura + Banco de Dados + API REST

**Cards do Kanban:** CARD-101, CARD-102, CARD-103
**Documentos necessários:** PRD (seções 2.1-2.13, 4.4), Spec Técnica (seção 4)

```
Você vai construir a base de infraestrutura do AgentFlow Studio, seguindo o
PRD_AgentFlow_Studio_v1_1.md (seção 4.4 para o modelo de dados) e a
Spec_Tecnica_Integracao_v1_0.md (seção 4 para a topologia de rede Docker).

TAREFA:
1. Crie o docker-compose.yml do AgentFlow Studio exatamente como especificado
   na seção 4 da Spec Técnica — incluindo a rede externa "firecrawl_backend"
   (não invente um nome de rede diferente).
2. Implemente o schema do banco de dados (SQLite + SQLAlchemy) com TODAS as
   entidades da seção 4.4 do PRD: User, Project, Card, Artifact, Execution,
   Snippet (com o campo license), UserPreference, BudgetLimit, ResearchCache.
3. Implemente os endpoints CRUD REST em FastAPI para Project e Card, com
   validação Pydantic e documentação automática via /docs.
4. Escreva testes cobrindo pelo menos os critérios de aceitação listados no
   PRD para essas features (procure "Critérios de Aceitação" nas seções
   correspondentes).

ANTES DE COMEÇAR:
- Se algum campo do modelo de dados parecer ambíguo (tipo de dado, se é
  obrigatório ou não), PARE e me pergunte em vez de assumir. Isso é
  propositalmente barato de corrigir agora e caro de corrigir depois.
- Não implemente autenticação de usuário completa ainda — use um stub simples
  (usuário único fixo) e me avise que isso precisa ser revisitado antes de
  qualquer deploy multi-usuário real.

DEFINIÇÃO DE PRONTO:
- docker compose up -d sobe sem erro e o healthcheck (/health) responde 200
- Todas as entidades da seção 4.4 do PRD existem no banco, incluindo as novas
  (UserPreference, BudgetLimit, ResearchCache, license em Snippet)
- Swagger em /docs mostra os endpoints CRUD de Project e Card
- Testes passam com >70% de cobertura nesses módulos
```

**Antes de começar:** confirme que você já rodou `docker compose up -d` no repositório do Firecrawl antes (a rede `firecrawl_backend` precisa existir antes do AgentFlow tentar se juntar a ela).

---

## PROMPT 2 — Fase 1b: Ideation Agent + Sistema de Execução

**Cards do Kanban:** CARD-105, CARD-106
**Documentos necessários:** Prompts_Agentes (seção 1), PRD (seção 2.2)

```
Agora vamos implementar o primeiro agente de verdade: o Ideation Agent.

TAREFA:
1. Use EXATAMENTE o prompt, o schema de input/output e o exemplo do
   Prompts_Agentes_AgentFlow_v0_1.md, seção 1 — não reescreva o prompt do
   zero, use o texto que já validamos manualmente no Prompt 0.
2. Implemente o endpoint POST /agents/ideation/run que recebe raw_idea,
   chama o LLM configurado (Gemini por padrão, mas deixe o provider
   configurável via variável de ambiente IDEATION_LLM_PROVIDER, seguindo o
   padrão de configuração por agente que discutimos), e salva o resultado
   como um Artifact vinculado ao Card.
3. Implemente o sistema de execução assíncrono (fila + worker) descrito na
   seção 2.5 do PRD (CARD-106): toda chamada de agente vira um job com
   status (pending/running/completed/failed), não uma chamada síncrona
   bloqueante.
4. Adicione timeout de 30s e retry de até 2x em caso de falha de rede/LLM,
   conforme os critérios de aceitação do PRD.

ANTES DE COMEÇAR:
- Se o schema de output do Ideation Agent no documento de prompts não bater
  exatamente com o que fizemos no teste manual do Prompt 0 (porque
  ajustamos o prompt lá), use a versão AJUSTADA, não a original do
  documento.
- Não pule a parte de "salvar como Artifact" achando que pode adicionar
  depois — o resto do pipeline depende de Artifacts existirem desde já.

DEFINIÇÃO DE PRONTO:
- POST /agents/ideation/run com uma ideia real retorna um job_id
- Consultar o status do job mostra o resultado estruturado quando completo
- O resultado é salvo como Artifact (type=json, agent_name=ideation_agent)
- Testar com uma ideia vaga: confidence_score cai de forma sensata
- Timeout/retry funcionam (teste desligando a API key temporariamente)
```

---

## PROMPT 3 — Fase 1c: Interface Kanban (Frontend)

**Cards do Kanban:** CARD-104
**Documentos necessários:** PRD (seções 2.1, 5)

```
Construa a interface Kanban real do produto (não confundir com o quadro de
gestão do próprio projeto — este é o board que o usuário final vai usar para
acompanhar suas ideias virando produto).

TAREFA:
1. React + Tailwind, seguindo as 6 colunas definidas no PRD seção 2.1:
   Backlog, Researching, Planning, Reviewing, Production, Done.
2. Cards arrastáveis entre colunas (drag-and-drop), refletindo mudança de
   status via chamada à API que construímos no Prompt 1.
3. Modal de detalhes do card mostrando os Artifacts gerados por cada agente,
   com uma aba por agente (conforme seção 5 do PRD — inclua a aba "Pesquisa"
   com o relatório do Research Agent e os avisos de licença do Code Research
   Agent).
4. Badge visual para "🤖 Auto-aprovado" quando aplicável (isso ainda não vai
   funcionar de verdade até implementarmos o HITL Gate no Prompt 6, mas
   deixe o componente pronto).

ANTES DE COMEÇAR:
- Confirme comigo o endpoint exato de listagem de cards com seus artifacts
  antes de montar as chamadas — se o Prompt 1 não deixou isso claro, pare e
  pergunte em vez de inventar o formato de resposta.

DEFINIÇÃO DE PRONTO:
- Board renderiza as 6 colunas com cards reais vindos da API
- Arrastar um card entre colunas persiste a mudança (recarregar a página
  mantém o novo status)
- Modal de detalhes abre e mostra os Artifacts existentes
- Design responsivo (funciona em tela de notebook e em tablet)
```

---

## PROMPT 4 — Fase 1d: Cliente MCP/REST + Circuit Breaker

**Cards do Kanban:** CARD-107
**Documentos necessários:** Spec Técnica (seções 1, 2, 3, 5)

```
Implemente os clientes de integração com o SRA e o Firecrawl.

TAREFA:
1. Use o esqueleto de código da Spec_Tecnica_Integracao_v1_0.md, seção 3
   (SRAClient, FirecrawlClient, CircuitBreaker) como ponto de partida — não
   reescreva do zero.
2. ANTES de finalizar o SRAClient: suba o SRA localmente
   (docker compose --profile firecrawl up -d no repositório
   smart-research-agent) e abra http://localhost:3458/docs. Confirme o
   endpoint real de pesquisa e o formato exato de request/response — a
   Spec Técnica marca isso como "⚠️ a confirmar", então essa confirmação é
   sua responsabilidade agora, não uma suposição a manter.
3. Implemente o circuit breaker conforme a tabela da seção 5 da Spec
   Técnica (abre após 3 falhas, fecha depois de 60s).
4. Escreva um teste de integração real: derrube o container do SRA de
   propósito e confirme que o AgentFlow Studio não trava, apenas degrada
   graciosamente (mensagem de "pesquisa indisponível").

ANTES DE COMEÇAR:
- Não implemente a ponte MCP (mcp-server.mjs) — ela não é necessária para
  comunicação backend-a-backend, conforme já decidido na Spec Técnica.
  Use REST direto.
- Se o endpoint real do SRA for diferente do que a Spec Técnica supôs
  (POST /api/research), atualize o próprio arquivo Spec_Tecnica_Integracao
  com o valor confirmado — não deixe a informação errada nele.

DEFINIÇÃO DE PRONTO:
- SRAClient.research() funciona contra o SRA real rodando localmente
- FirecrawlClient.scrape() funciona contra o Firecrawl real rodando
  localmente
- Circuit breaker testado (3 falhas seguidas → abre; espera 60s → fecha)
- Spec_Tecnica_Integracao_v1_0.md atualizada com os valores confirmados
```

---

## PROMPT 5 — Fase 2a: Research Agent + Code Research Agent

**Cards do Kanban:** CARD-201, CARD-202
**Documentos necessários:** Prompts_Agentes (seções 2, 3), PRD (2.3, 2.4), Spec Técnica (seção 2)

```
Implemente o Research Agent e o Code Research Agent.

TAREFA:
1. Research Agent: use o prompt da seção 2.4 do Prompts_Agentes (ajustado
   conforme validamos no Prompt 0) para gerar a query, depois chame o
   SRAClient do Prompt 4. Implemente o cache de pesquisa (ResearchCache,
   7 dias) descrito no PRD seção 2.3.
2. Code Research Agent: para os repositórios candidatos retornados pelo
   SRA, busque README + estrutura de pastas via GitHub API (não via
   Firecrawl — GitHub API é mais rápido e barato para conteúdo dentro do
   github.com, conforme decidido). Use o Firecrawl apenas quando houver
   conteúdo relevante fora do domínio github.com.
3. Implemente a classificação de licença conforme o prompt da seção 3.4 do
   Prompts_Agentes — teste especificamente com um repositório AGPL de
   verdade (pode usar o próprio Firecrawl como caso de teste) para confirmar
   que o aviso aparece.
4. Timeout de 90s no Research Agent (não 45s — valor corrigido na Spec
   Técnica seção 1.6).

ANTES DE COMEÇAR:
- GITHUB_TOKEN precisa estar configurado — sem ele, o rate limit da API do
  GitHub vai quebrar isso rapidamente em uso real. Confirme que a variável
  de ambiente está documentada no .env.example do AgentFlow Studio.

DEFINIÇÃO DE PRONTO:
- Rodar o pipeline com uma ideia real gera um relatório de pesquisa salvo
  como Artifact
- Cache funciona: rodar a mesma ideia duas vezes em menos de 7 dias não
  chama o SRA de novo na segunda vez
- Code Research Agent classifica corretamente pelo menos 1 repo MIT e 1
  repo AGPL de teste
- Se o SRA estiver fora do ar, o card recebe o aviso, sem travar o pipeline
```

---

## PROMPT 6 — Fase 2b: Planner + Reviewer + Dev Agent + Sandbox

**Cards do Kanban:** CARD-203, CARD-204, CARD-205
**Documentos necessários:** Prompts_Agentes (seções 4, 5, 6), PRD (2.5, 2.6, 2.7)

```
Implemente o Planner Agent, o Reviewer Agent, e o Dev Agent com sandbox de
validação. Esta é a parte mais sensível do pipeline — capriche na parte de
autocorreção.

TAREFA:
1. Planner Agent: use o prompt da seção 4.4 do Prompts_Agentes. Confirme
   que ele recebe research_output e code_research_outputs como input, não
   só a ideia (isso mudou em relação a uma versão anterior do design).
2. Reviewer Agent: use o prompt da seção 5.4. Ele NÃO bloqueia o pipeline —
   os alertas aparecem no modal de aprovação, mas o usuário decide se segue.
3. Dev Agent: use o prompt da seção 6.4 para geração inicial, gerando por
   camada (backend, frontend, database, tests) como jobs separados.
4. Sandbox: implemente a execução em container efêmero (docker run --rm,
   sem rede externa, sem acesso a env vars sensíveis do host) conforme PRD
   seção 2.7. Se falhar, use o prompt de autocorreção da seção 6.5 do
   Prompts_Agentes, com no máximo 2 tentativas.

ANTES DE COMEÇAR:
- O sandbox roda com Docker-in-Docker ou chamando o Docker do host? Essa é
  uma decisão de arquitetura que a Spec Técnica não cobriu — pare e me
  pergunte antes de implementar, porque isso afeta a configuração de
  segurança do container.
- Não pule o teste de "falhar de propósito" — force um erro no código
  gerado manualmente para confirmar que o ciclo de autocorreção realmente
  funciona antes de considerar isso pronto.

DEFINIÇÃO DE PRONTO:
- Pipeline completo (Ideation → Research → Code Research → Planner →
  Reviewer → Dev) roda de ponta a ponta com uma ideia real
- Código gerado passa no sandbox sem edição manual em pelo menos 1 dos 3
  casos de teste
- Um caso forçado a falhar aciona a autocorreção e loga o stderr
  corretamente
- Depois de 2 tentativas falhas, o card mostra o aviso claro ao usuário
  (não trava silenciosamente)
```

---

## PROMPT 7 — Fase 2c: HITL Gate + Auto-approve + Preferências + Orçamento

**Cards do Kanban:** CARD-206, CARD-207, CARD-208, CARD-209
**Documentos necessários:** PRD (2.8, 2.9, 2.10, 2.11)

```
Implemente as features de controle humano e personalização.

TAREFA:
1. Human-in-the-Loop Gate: modal de aprovação (aprovar/rejeitar/editar),
   timeout de 24h, undo de 5min — conforme PRD seção 2.8.
2. Auto-approve: se confidence_score >= 0.85 E o Reviewer não gerou alerta
   "critical", avança automaticamente com janela de reversão de 30min.
   Adicione um toggle nas configurações para desativar isso globalmente.
3. Perfil de Preferências: sempre que o usuário editar ou rejeitar um
   artifact do Planner/Dev, registre o par (atributo, valor) na tabela
   UserPreference. Aplique no prompt do Planner/Dev apenas quando
   confidence_count >= 2 (use o template de injeção da seção 7 do
   Prompts_Agentes).
4. Cap de Orçamento: limite configurável mensal e por projeto, aviso em
   80%, bloqueio em 100%.

ANTES DE COMEÇAR:
- A lógica de "o que conta como uma preferência" a partir de uma edição
  livre de texto não é trivial de extrair de forma confiável — proponha
  primeiro uma abordagem simples (ex: diff estruturado de campos
  conhecidos, tipo "framework de teste", em vez de tentar interpretar
  edições de texto livre em geral) e me mostre antes de implementar.

DEFINIÇÃO DE PRONTO:
- Aprovar/rejeitar/editar um card funciona e é refletido no board
- Um card com confidence alto e sem alertas críticos avança sozinho, e é
  revertível por 30min
- Editar a stack recomendada do Planner 2x com o mesmo valor cria uma
  UserPreference com confidence_count=2, e ela aparece no próximo Planner
  Agent chamado
- Atingir 80% do orçamento gera aviso; atingir 100% bloqueia novas execuções
```

---

## PROMPT 8 — Fase 3: Polish e Deploy

**Cards do Kanban:** CARD-301 a CARD-304
**Documentos necessários:** PRD (2.12, 2.13, seção 4)

```
Finalize os itens de polish e prepare o deploy.

TAREFA:
1. Dashboard de métricas simplificado (PRD seção 2.13): cards de projetos/
   custo/tempo, tabela de execuções com filtros — sem gráficos ainda.
2. Onboarding: pode ser um guia em texto/vídeo curto por enquanto (a versão
   de tour interativo foi rebaixada para P1, não é bloqueante).
3. UX polish: loading states, empty states, dark mode.
4. Deploy: prepare o ambiente para ir do Docker Desktop para uma VPS,
   usando as variáveis de ambiente (SRA_BASE_URL, FIRECRAWL_BASE_URL) já
   configuradas para não depender de localhost.

ANTES DE COMEÇAR:
- Não implemente billing/pagamento — está fora de escopo do MVP (PRD,
  seção "Out-of-Scope", F-020).
- Confirme comigo qual VPS/provedor antes de escrever scripts de deploy
  específicos — isso muda bastante a implementação.

DEFINIÇÃO DE PRONTO:
- Dashboard mostra métricas reais de um projeto completo
- Aplicação sobe em um ambiente limpo (VM nova) seguindo só o README
- Nenhuma variável de ambiente com localhost hardcoded no código
```

---

## Nota Final

Estes 9 prompts cobrem as Fases 0 a 3 do Kanban. A Fase 3.5 (Go-to-Market e Beta Launch, CARD-401/402) é essencialmente trabalho humano — divulgação, comunidade, conversas com beta testers — e não faz sentido delegar isso para uma IA de código; use o PRD e o Kanban como checklist nessa etapa, não como prompt de execução.

Se em algum prompt a IA de código se desviar do que está documentado (inventar um endpoint, ignorar um critério de aceitação, pular a seção "Antes de começar"), o sinal mais confiável de que algo deu errado é justamente isso: a saída dela deixar de bater com o que está escrito nos 4 documentos. Volte ao documento, não à memória da conversa, para resolver a divergência.
