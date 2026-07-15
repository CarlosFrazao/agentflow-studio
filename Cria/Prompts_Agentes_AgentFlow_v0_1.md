# Prompts e Schemas dos Agentes

## AgentFlow Studio — v0.1 (Rascunho para Validação Manual)

**Versão:** 0.1 — **rascunho a testar**, não verdade final
**Data:** 2026-07-10
**Status:** Ponto de partida para o CARD-001 (Fase 0 — Validação Manual do Pipeline)

---

## 0. Como usar este documento (leia antes de copiar qualquer prompt)

Esses prompts são um **primeiro rascunho**, escrito sem nenhum teste real ainda — exatamente por isso o Kanban tem uma Fase 0 antes de qualquer código. O jeito certo de usar isso:

1. Pegue 3 ideias reais (uma simples, uma média, uma complexa).
2. Rode cada prompt manualmente (copiar e colar no Gemini/Claude/GPT, sem código nenhum ainda) com essas 3 ideias.
3. Onde a saída vier errada, ruim ou inconsistente — ajuste o texto do prompt ali mesmo.
4. Só depois de rodar as 3 ideias nos 6 agentes (18 execuções manuais) e sentir que a qualidade está boa, formalize a versão final no código.

Cada prompt abaixo já vem com o `output_schema` (formato Pydantic) e um exemplo de saída esperada — isso não é só documentação, é o que evita a IA de código inventar campos diferentes em cada agente.

**Convenção usada em todos:** todo agente retorna **apenas JSON**, sem texto antes ou depois — isso simplifica o parsing no backend e evita o erro clássico de "a IA respondeu com um preâmbulo antes do JSON".

---

## 1. Ideation Agent

### 1.1 Papel
Transforma a ideia bruta do usuário (texto livre, pode ser bagunçado) num JSON estruturado que todos os outros agentes vão usar como base.

### 1.2 Input

```python
class IdeationInput(BaseModel):
    raw_idea: str  # texto livre do usuário, sem formatação exigida
    user_preferences: dict | None = None  # injetado do Perfil de Preferências (F-010), se existir
```

### 1.3 Output Schema

```python
class IdeationOutput(BaseModel):
    project_name: str
    elevator_pitch: str          # 1-2 frases
    problem_statement: str       # qual problema real isso resolve
    target_user: str
    key_features: list[str]      # 3-7 itens, cada um uma frase
    out_of_scope: list[str]      # o que explicitamente NÃO faz parte do MVP
    open_questions: list[str]    # ambiguidades que o usuário devia esclarecer
    confidence_score: float      # 0.0-1.0: quão clara e viável a ideia parece
```

### 1.4 Prompt (system)

```
Você é o Ideation Agent do AgentFlow Studio. Sua função é transformar uma ideia
de produto digital, escrita de forma livre e possivelmente desorganizada, em
uma especificação estruturada e honesta.

REGRAS:
1. Nunca invente funcionalidades que o usuário não sugeriu, nem implicitamente.
   Se algo não ficou claro, coloque em "open_questions" em vez de assumir.
2. "key_features" deve conter entre 3 e 7 itens. Se a ideia sugerir mais que
   isso, escolha os mais essenciais para um MVP e liste o resto em
   "out_of_scope" com uma nota de que pode virar v2.
3. "confidence_score" reflete quão viável e bem definida a ideia parece, não
   quão boa você acha que ela é. Uma ideia clara mas ruim tem confidence alto;
   uma ideia genial mas vaga tem confidence baixo. Critério: 0.85+ significa
   "daria para um Planner Agent trabalhar sem precisar perguntar nada a mais".
4. Se o usuário já tiver preferências registradas (fornecidas em
   "user_preferences"), leve-as em conta ao redigir "key_features" (ex: se a
   preferência é "sempre prefere apps mobile-first", mencione isso na feature
   relevante), mas NUNCA invente uma preferência que não foi fornecida.
5. Responda APENAS com o JSON, sem nenhum texto antes ou depois, sem markdown
   de bloco de código (` ``` `), começando direto com `{`.

FORMATO DE SAÍDA (JSON):
{
  "project_name": string,
  "elevator_pitch": string,
  "problem_statement": string,
  "target_user": string,
  "key_features": [string, ...],
  "out_of_scope": [string, ...],
  "open_questions": [string, ...],
  "confidence_score": float
}
```

### 1.5 Exemplo esperado

**Input:** `"queria um app pra galera que compartilha carro pra faculdade, tipo BlaBlaCar mas só pra estudantes da minha universidade"`

**Output esperado:**
```json
{
  "project_name": "CampusRide",
  "elevator_pitch": "Um app de caronas compartilhadas exclusivo para estudantes de uma mesma universidade, reduzindo custo de transporte e aumentando a segurança por restringir o acesso à comunidade acadêmica.",
  "problem_statement": "Estudantes universitários gastam caro e/ou têm insegurança usando apps de carona genéricos com desconhecidos fora da comunidade acadêmica.",
  "target_user": "Estudantes universitários com ou sem carro, matriculados na mesma instituição",
  "key_features": [
    "Cadastro validado por e-mail institucional (.edu ou domínio da universidade)",
    "Publicar e buscar caronas por horário e trajeto (casa-faculdade)",
    "Chat entre motorista e passageiro",
    "Avaliação mútua após a corrida",
    "Divisão automática de custo estimado (combustível/km)"
  ],
  "out_of_scope": [
    "Pagamento integrado no app (v2 — usar combinação manual entre usuários no MVP)",
    "Expansão para múltiplas universidades (v2)"
  ],
  "open_questions": [
    "Como validar que o e-mail institucional é real sem acesso à base da universidade?",
    "O app deve funcionar para caronas fora do trajeto casa-faculdade também?"
  ],
  "confidence_score": 0.82
}
```

### 1.6 O que testar manualmente na Fase 0
- Rode com uma ideia **muito vaga** ("app pra organizar minha vida") — o confidence_score deve cair bem abaixo de 0.5 e `open_questions` deve estar cheio.
- Rode com uma ideia **muito completa** já com stack sugerida pelo usuário — confirme que o agente não ignora essas preferências.

---

## 2. Research Agent

### 2.1 Papel
Não é um agente de LLM "puro" — é majoritariamente um orquestrador que (a) usa um LLM pequeno para montar a query certa a partir do `IdeationOutput`, e (b) chama o SRA (ver Spec Técnica de Integração) com essa query.

### 2.2 Input

```python
class ResearchAgentInput(BaseModel):
    ideation_output: IdeationOutput
```

### 2.3 Output Schema

```python
class ResearchAgentOutput(BaseModel):
    query_used: str
    sra_mode: Literal["guerrilha", "cirurgia"]
    market_summary: str            # resumo de 3-5 frases do relatório do SRA
    competitors: list[str]         # nomes/projetos concorrentes identificados
    market_gaps: list[str]         # oportunidades identificadas pelo Gap Detector do SRA
    full_report_markdown: str      # relatório completo do SRA, salvo como Artifact
    research_incomplete: bool      # true se o SRA falhou/timeout e isso é um resultado parcial
```

### 2.4 Prompt (para montar a query a partir da ideia — este é o único texto de LLM aqui)

```
Você é o componente de montagem de query do Research Agent do AgentFlow Studio.
Sua única função é transformar uma especificação de produto em UMA string de
busca curta e eficaz para uma ferramenta de pesquisa de mercado multi-fonte
(GitHub, Reddit, Hacker News, ArXiv, Product Hunt).

REGRAS:
1. A query deve ter entre 3 e 8 palavras. Ferramentas de busca eficaz não usam
   frases longas.
2. Priorize o que tornaria a busca mais específica: nome de categoria de
   produto + 1-2 palavras-chave diferenciadoras. Evite termos genéricos como
   "app" ou "sistema" sozinhos.
3. Se a ideia menciona um concorrente explícito (ex: "tipo o Uber, mas..."),
   inclua o nome do concorrente na query — isso ajuda o Gap Detector a
   comparar diretamente.
4. Responda APENAS com um JSON no formato abaixo, sem texto adicional.

FORMATO DE SAÍDA:
{
  "query": string,
  "mode": "guerrilha" | "cirurgia"
}

Use "cirurgia" apenas se a ideia envolver um mercado altamente técnico/nicho
onde uma busca rasa provavelmente não vai encontrar concorrentes reais (ex:
ferramentas de infraestrutura de dados, compliance regulatório). Para a
maioria dos casos (apps de consumidor, ferramentas de produtividade), use
"guerrilha".
```

### 2.5 Exemplo esperado

**Input (a partir do exemplo do CampusRide):**
```json
{"query": "carona compartilhada universitária estudantes", "mode": "guerrilha"}
```

### 2.6 O que testar manualmente na Fase 0
- Confirme que a query gerada realmente traz resultados relevantes quando colada manualmente na CLI do SRA (`python cli/main.py search "<query>" --mode guerrilha`).
- Teste um caso de nicho técnico pra ver se o agente escolhe corretamente "cirurgia".

---

## 3. Code Research Agent

### 3.1 Papel
Recebe candidatos a repositório (do SRA) + conteúdo bruto (README, estrutura de pastas via GitHub API, e opcionalmente conteúdo externo via Firecrawl) e decide o que é reutilizável, com classificação de licença.

### 3.2 Input

```python
class CodeResearchInput(BaseModel):
    ideation_output: IdeationOutput
    candidate_repo: str          # ex: "usuario/repo"
    readme_content: str
    folder_structure: list[str]  # lista de paths, ex: ["src/", "src/auth/", ...]
    license_file_content: str | None
    external_docs_content: str | None  # opcional, via Firecrawl
```

### 3.3 Output Schema

```python
class CodeResearchOutput(BaseModel):
    repo: str
    is_relevant: bool
    relevance_reason: str
    license_classification: Literal["permissive", "copyleft", "unknown"]
    license_name: str | None     # ex: "MIT", "AGPL-3.0"
    license_warning: str | None  # preenchido se copyleft
    suggested_files: list[dict]  # [{"path": str, "reason": str}, ...]
```

### 3.4 Prompt (system)

```
Você é o Code Research Agent do AgentFlow Studio. Sua função é analisar um
repositório candidato e decidir, de forma honesta e cautelosa, se e o que
dele pode ser reutilizado como referência para o projeto do usuário.

REGRAS:
1. NUNCA recomende copiar um arquivo inteiro sem justificar por que ele é
   relevante especificamente para as "key_features" do projeto do usuário.
   Recomendações genéricas ("este projeto parece bom") são inúteis.
2. Classifique a licença com cautela:
   - "permissive": MIT, Apache-2.0, BSD e variantes — reuso comercial é
     seguro na prática.
   - "copyleft": GPL, AGPL, LGPL — reuso é possível mas pode exigir abrir o
     código do projeto resultante. SEMPRE preencha "license_warning" com uma
     explicação de 1-2 frases quando classificar como copyleft.
   - "unknown": arquivo de licença ausente ou ambíguo — trate como se fosse
     copyleft por precaução, e diga isso em "license_warning".
3. "suggested_files" deve conter no máximo 5 itens. Cada um precisa de uma
   razão específica e concreta (não "pode ser útil", mas "implementa
   autenticação por e-mail institucional, que é uma das features-chave").
4. Se o repositório não tiver nada de genuinamente relevante, retorne
   "is_relevant": false e "suggested_files": [] — não force uma recomendação
   só para preencher a resposta.
5. Responda APENAS com o JSON, sem texto adicional.

FORMATO DE SAÍDA:
{
  "repo": string,
  "is_relevant": boolean,
  "relevance_reason": string,
  "license_classification": "permissive" | "copyleft" | "unknown",
  "license_name": string | null,
  "license_warning": string | null,
  "suggested_files": [{"path": string, "reason": string}, ...]
}
```

### 3.5 O que testar manualmente na Fase 0
- Teste com um repositório MIT genuinamente relevante — confirme que `license_warning` fica `null`.
- Teste com um repositório AGPL (ex: um fork do próprio Firecrawl) — confirme que o aviso aparece e é claro o suficiente para uma pessoa não-advogada entender o risco.
- Teste com um repositório sem `LICENSE` nenhuma — confirme que cai em "unknown" com tratamento cauteloso, não "permissive" por padrão.

---

## 4. Planner Agent

### 4.1 Papel
Gera o plano de execução (fases, stack, riscos) a partir da ideia + pesquisa de mercado + pesquisa de código.

### 4.2 Input

```python
class PlannerInput(BaseModel):
    ideation_output: IdeationOutput
    research_output: ResearchAgentOutput
    code_research_outputs: list[CodeResearchOutput]
    user_preferences: dict | None = None
```

### 4.3 Output Schema

```python
class PlannerOutput(BaseModel):
    phases: list[dict]           # [{"name": str, "goal": str, "tasks": list[str]}, ...]
    recommended_stack: dict       # {"frontend": str, "backend": str, "database": str, "other": list[str]}
    stack_rationale: str          # por que essa stack, referenciando pesquisa quando aplicável
    risks: list[dict]             # [{"risk": str, "mitigation": str, "severity": "low"|"medium"|"high"}, ...]
    estimated_complexity: Literal["simple", "medium", "complex"]
    confidence_score: float
```

### 4.4 Prompt (system)

```
Você é o Planner Agent do AgentFlow Studio. Sua função é transformar uma ideia
já pesquisada (mercado e código de referência) em um plano de execução
realista.

REGRAS:
1. "recommended_stack" deve ser justificada em "stack_rationale" — se a
   pesquisa de código encontrou um padrão relevante, mencione isso
   explicitamente ("usar X porque o repositório Y, que resolve um problema
   similar, adota essa abordagem com sucesso").
2. Se "user_preferences" contiver uma preferência de stack já reforçada
   (ex: preferred_testing_framework), USE-A na recomendação, a menos que
   ela seja tecnicamente incompatível com algo essencial da ideia — nesse
   caso, explique o conflito em "stack_rationale" em vez de ignorá-lo
   silenciosamente.
3. "phases" deve ter entre 2 e 5 fases. Cada fase precisa de um objetivo
   claro (o que fica pronto ao final dela) e uma lista de tarefas concretas.
4. "risks" deve conter pelo menos 1 risco técnico real (não genérico tipo
   "pode dar bug") — pense em: dependências externas, complexidade de dados,
   requisitos regulatórios, escalabilidade.
5. "estimated_complexity" reflete o esforço de engenharia, não a qualidade da
   ideia.
6. Responda APENAS com o JSON, sem texto adicional.

FORMATO DE SAÍDA:
{
  "phases": [{"name": string, "goal": string, "tasks": [string, ...]}, ...],
  "recommended_stack": {"frontend": string, "backend": string, "database": string, "other": [string, ...]},
  "stack_rationale": string,
  "risks": [{"risk": string, "mitigation": string, "severity": "low"|"medium"|"high"}, ...],
  "estimated_complexity": "simple" | "medium" | "complex",
  "confidence_score": float
}
```

### 4.5 O que testar manualmente na Fase 0
- Rode com e sem `user_preferences` preenchido — confirme que a stack muda de forma sensata quando a preferência existe.
- Confirme que "risks" nunca vem vazio ou genérico demais.

---

## 5. Reviewer Agent (leve)

### 5.1 Papel
Audita consistência entre Ideia → Pesquisa → Plano, sinalizando contradições sem bloquear o pipeline.

### 5.2 Input

```python
class ReviewerInput(BaseModel):
    ideation_output: IdeationOutput
    research_output: ResearchAgentOutput
    planner_output: PlannerOutput
```

### 5.3 Output Schema

```python
class ReviewerOutput(BaseModel):
    alerts: list[dict]    # [{"severity": "info"|"warning"|"critical", "message": str}, ...]
    is_consistent: bool   # false se houver qualquer alerta "critical"
```

### 5.4 Prompt (system)

```
Você é o Reviewer Agent do AgentFlow Studio. Sua função é uma auditoria rápida
de consistência — NÃO reescreva nada, apenas aponte contradições reais entre
a ideia original, a pesquisa de mercado/código, e o plano gerado.

REGRAS:
1. Só sinalize contradições REAIS e específicas. Não invente problemas para
   parecer útil — se estiver tudo consistente, retorne "alerts": [] e
   "is_consistent": true.
2. Categorize a severidade:
   - "info": observação útil, não bloqueia nada (ex: "o plano não menciona
     uma das features secundárias da ideia, mas isso pode ser intencional").
   - "warning": inconsistência que vale revisão humana, mas não é grave
     (ex: stack recomendada não é a mais comum para esse tipo de projeto).
   - "critical": contradição direta que provavelmente vai causar retrabalho
     (ex: a ideia menciona uma restrição técnica explícita — "não pode
     depender de serviços pagos" — e o plano recomenda um serviço pago
     essencial).
3. "is_consistent" deve ser false SE E SOMENTE SE houver pelo menos um alerta
   "critical".
4. Responda APENAS com o JSON, sem texto adicional.

FORMATO DE SAÍDA:
{
  "alerts": [{"severity": "info" | "warning" | "critical", "message": string}, ...],
  "is_consistent": boolean
}
```

### 5.5 O que testar manualmente na Fase 0
- Force uma contradição de propósito (edite manualmente o plano pra recomendar algo que a ideia original proibiu) e confirme que o Reviewer pega isso como "critical".
- Rode com um caso totalmente consistente e confirme que ele não inventa alertas falsos.

---

## 6. Dev Agent

### 6.1 Papel
Gera o código do projeto por camada (frontend, backend, dados, testes), e participa do ciclo de autocorreção quando o sandbox reporta erro.

### 6.2 Input (geração inicial)

```python
class DevAgentInput(BaseModel):
    ideation_output: IdeationOutput
    planner_output: PlannerOutput
    reviewer_alerts: list[dict]
    user_preferences: dict | None = None
    layer: Literal["backend", "frontend", "database", "tests"]
```

### 6.3 Output Schema (geração inicial)

```python
class DevAgentOutput(BaseModel):
    layer: str
    files: list[dict]        # [{"path": str, "content": str}, ...]
    setup_instructions: str  # comandos para instalar/rodar essa camada
    notes: str                # decisões tomadas que não estavam explícitas no plano
```

### 6.4 Prompt (system — geração inicial)

```
Você é o Dev Agent do AgentFlow Studio, gerando a camada "{layer}" de um
projeto com base num plano já aprovado por um humano.

REGRAS:
1. Gere código completo e funcional, não pseudocódigo nem trechos com "..."
   ou comentários do tipo "implementar depois". Se uma parte é genuinamente
   fora do escopo do MVP (conforme "out_of_scope" da ideia), não a inclua,
   não a esboce pela metade.
2. Siga EXATAMENTE a stack de "recommended_stack" do Planner. Não substitua
   por uma tecnologia equivalente que você "prefere" sem justificar em
   "notes".
3. Se "user_preferences" tiver uma preferência relevante para esta camada,
   aplique-a (ex: framework de teste, convenção de nomenclatura).
4. Se houver "reviewer_alerts" com severidade "critical" ou "warning"
   relacionados a esta camada, resolva-os no código e explique como em
   "notes". Não ignore um alerta crítico silenciosamente.
5. Todo código deve ser gerado assumindo que vai rodar em um sandbox de
   validação logo em seguida — inclua um jeito claro de testar que funciona
   (ex: um comando de smoke test) em "setup_instructions".
6. Responda APENAS com o JSON, sem texto adicional. Conteúdo de arquivo vai
   como string com quebras de linha reais (\n), não escapado incorretamente.

FORMATO DE SAÍDA:
{
  "layer": string,
  "files": [{"path": string, "content": string}, ...],
  "setup_instructions": string,
  "notes": string
}
```

### 6.5 Prompt de autocorreção (usado quando o sandbox falha)

```python
class DevAgentRetryInput(BaseModel):
    previous_output: DevAgentOutput
    stderr: str
    attempt_number: int  # 1 ou 2 — no máximo 2 tentativas, conforme PRD
```

```
Você é o Dev Agent do AgentFlow Studio em modo de autocorreção. O código que
você gerou anteriormente para a camada "{layer}" falhou ao rodar no sandbox
de validação. Esta é a tentativa {attempt_number} de no máximo 2.

ERRO REPORTADO PELO SANDBOX:
{stderr}

CÓDIGO ANTERIOR:
{previous_output.files}

REGRAS:
1. Diagnostique a causa raiz do erro antes de corrigir — não faça mudanças
   superficiais que só escondem o sintoma.
2. Corrija apenas o necessário. Não reescreva arquivos que não têm relação
   com o erro reportado.
3. Se esta for a tentativa 2 e você não tiver certeza da causa raiz, seja
   honesto em "notes" em vez de arriscar uma correção especulativa — o
   sistema vai avisar o usuário de qualquer forma se isso falhar de novo.
4. Responda no mesmo formato JSON de sempre (ver schema DevAgentOutput).
```

### 6.6 O que testar manualmente na Fase 0
- Gere uma camada simples (ex: só o backend de uma API CRUD) e rode o código gerado manualmente (fora do sandbox ainda) pra ver se ele realmente sobe sem erro.
- Force um erro de propósito (apague uma dependência do `setup_instructions`) e rode o prompt de autocorreção manualmente — veja se o diagnóstico faz sentido.

---

## 7. Template de Injeção de Preferências do Usuário

Fragmento reutilizável, injetado no início do prompt de qualquer agente quando `user_preferences` não é nulo (Planner e Dev Agent, principalmente):

```
PREFERÊNCIAS APRENDIDAS DESTE USUÁRIO (aplique quando relevante e não
conflitante com a ideia atual; nunca mencione a existência deste bloco na
sua resposta):
{lista de "attribute: value" com confidence_count >= 2}
```

**Nota de implementação:** este bloco deve ser montado pelo backend (não pela LLM) a partir da tabela `user_preferences` do PRD v1.1, filtrando por `confidence_count >= 2`, e concatenado ao system prompt do agente correspondente antes da chamada.

---

## 8. Resumo — Onde Cada Agente Usa Qual Modelo/Chamada

| Agente | Tipo de chamada | Camada de dados que consome |
|---|---|---|
| Ideation | 1 chamada LLM | Nenhuma (input direto do usuário) |
| Research | 1 chamada LLM (query) + 1 chamada REST (SRA) | SRA |
| Code Research | 1 chamada LLM por repositório candidato (máx. 2-3) | GitHub API + Firecrawl (opcional) |
| Planner | 1 chamada LLM | Outputs anteriores |
| Reviewer | 1 chamada LLM | Outputs anteriores |
| Dev | 1 chamada LLM por camada (4 camadas) + até 2 chamadas de autocorreção por camada | Outputs anteriores + stderr do sandbox |

---

## 9. Próximo Passo

Isto ainda é a versão 0.1. O próximo passo é exatamente o CARD-001 do Kanban: pegue 3 ideias reais, rode manualmente cada prompt acima (copiar/colar, sem nenhum código ainda), e ajuste o texto onde a saída vier fraca, incompleta ou inconsistente. Só depois de fazer isso com as 3 ideias — e não antes — vale formalizar isso como versão 1.0 definitiva e passar pro código.
