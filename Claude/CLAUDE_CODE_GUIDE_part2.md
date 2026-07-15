# 📖 Guia Supremo do Claude Code (Parte 2)

> **Continuacao da Parte 1.**

---


## 🎯 Resumo da Cartilha de Sobrevivência de Tokens
1.  **Sessões Curtas:** Inicie tarefas específicas com `/clear`.
2.  **Raciocínio Controlado:** Use **`Alt + T`** ou `/effort low` para tarefas de rotina, `medium` para codificação principal e `max` para arquitetura inicial.
3.  **Limpeza Constante:** Digite `/compact` a cada 10 a 15 interações.
4.  **Enxágue de MCPs:** Mantenha apenas os plugins estritamente necessários no seu `/mcp`.
5.  **Perguntas Paralelas:** Prefira sempre usar `/btw <sua dúvida>` para esclarecer dúvidas lógicas ou de arquitetura sem poluir o histórico nem gastar sua cota com conversas paralelas.
6.  **Decisões Complexas (Ultra Plan):** Para planejar grandes refatorações ou features difíceis de backend que afetem múltiplos arquivos, acione o `/ultraplan` para estruturar a lógica na web de forma milimétrica antes de codificar.
7.  **Comandos Customizados:** Use `/api-validate` e `/task-sync` para automatizar tarefas sem precisar explicá-las em prompts.
8.  **Comandos Nativos com `!`:** Execute scripts e comandos do sistema no terminal usando o prefixo `!` para gastar zero tokens com a LLM.
9.  **Foco em Erros Enxutos:** Copie e envie apenas as primeiras 5-10 linhas de erros e traces no console para economizar tokens de entrada.
10. **Aproveite o Prompt Caching:** Trabalhe em blocos de foco contínuo. Pausas de mais de 5 minutos fazem o cache da Anthropic expirar, gerando uma cobrança de gravação na próxima mensagem.
11. **Estilo Caveman de Output:** Adote o modo de saída conciso (instalando a skill ou pedindo no prompt) para reduzir até 75% dos tokens de saída e aumentar a velocidade em 3x.
12. **Ciclo de Rigor Gstack:** Nunca construa código sem planejamento prévio. Empregue as personas de CEO (UX), Eng (Escala) e CSO (Segurança) ativamente para blindar o código contra amadorismos de vibe coding.
13. **Atalhos e Queuing de Terminal:** Utilize **`Shift + Tab`** para alternar de modo, a mira telescópica **`@`** para arquivos específicos, e o **enfileiramento de prompts** em background para corrigir a IA sem tokens perdidos.
14. **Automatize com Hooks e Subagentes:** Mapeie tarefas de build no `settings.json` (hooks) e crie subagentes em `.claude/agents/` para paralelizar testes e auditorias complexas sem intervenção manual.
15. **Context7 para Documentações Blindadas:** Em Next.js e Prisma, use documentações blindadas com o Context7 (MCP dinâmico ou, preferencialmente, o **Skill Wizard** local em `.claude/skills/`) para eliminar alucinações e erros de compatibilidade de versões.
16. **O Rigor Karpathy Local:** Nunca permita que a IA tome decisões silenciosas em prompts vagos ou inche o diff. Invoque a disciplina de código mínimo e exija que ela pare e pergunte diante de tradeoffs de design ou escopo.
17. **Desenvolvimento Autônomo com `/go`:** Para auditorias longas de segurança, testes em lote ou refatorações profundas, despache o Claude sob o comando autônomo `/go` em background, definindo um DoD claro e um critério de parada física mensurável.
18. **Detalhamento Preciso de Ações Delegadas (Anti-Confusão de Repositórios):** Ao passar instruções Git ou comandos de terminal de ecossistema para o Claude (ex: commit, push), o orquestrador/usuário deve ser explícito em relação ao escopo das pastas de repositórios aninhados e flags de segurança, sempre instruindo de forma sequencial (ex: "Acesse a pasta X, rode 'git add -A', execute 'git commit...'") para evitar vazamento acidental de chaves de API do `.env` da raiz e commits em diretórios indesejados.
19. **Idioma de Comunicação Obrigatório (PT-BR):** O Claude deve falar e interagir com o usuário sempre em Português do Brasil (PT-BR). Os códigos, comentários no código e especificações técnicas internas devem ser mantidos em Inglês (EN) para manter o padrão profissional do repositório.

Comando para dar permissão total --> claude --dangerously-skip-permissions

---

## 🛡️ 15. Framework ZEUS de Vigilância por Blocos

> **Origem:** Metodologia de vigilância contínua para projetos de IA.
> **Aplicabilidade:** Qualquer projeto com múltiplos blocos/features que precisem de vigilância contínua da IA.

### 💡 Conceito Central: Vigilância ZEUS 24/7

O **ZEUS** é um sistema de vigilância aplicado em **4 momentos obrigatórios** de cada bloco:

| Momento | Quando Ocorre | O que Valida |
|---------|--------------|-------------|
| **PRE-CHECK ZEUS** | Antes de começar o bloco | Dependências satisfeitas? Especificação clara? Skills certas? |
| **MID-CHECK ZEUS** | Durante a execução | Código entregue completo? Nenhum arquivo omitido? |
| **POST-CHECK ZEUS** | Após implementar | Anti-TODO, Anti-Botão-Morto, Anti-Genérico, Prova de Vida |
| **HANDOFF-AUDIT ZEUS** | Ao finalizar o bloco | Handoff log completo? Próximo agente consegue continuar sem perguntas? |

### 🔥 Os 3 Anti-Padrões PROIBIDOS (Post-Check obrigatório)

```
[ ] Anti-TODO:     Zero TODOs, FIXMEs, placeholders, funções vazias no código entregue.
[ ] Anti-Botão-Morto: Todo botão/ação tem função real, aria-label e API conectada.
[ ] Anti-Genérico: Zero SQL raw, zero hardcoded secrets no código entregue.
```

**Como rodar a varredura Anti-TODO sem gastar tokens:**
```bash
!grep -rn "TODO\|FIXME\|HACK" src/ --include="*.py"
```
> Deve retornar **ZERO** linhas. Se retornar qualquer resultado = **REPROVAÇÃO IMEDIATA**.

### 🔪 Vertical Slicing (1 Feature = 1 Bloco = 1 Sessão Claude)

A estratégia de **Vertical Slicing** garante que cada sessão do Claude entregue uma feature **100% vertical** — do núcleo às APIs — sem deixar pontas soltas:

```
ESTRUTURA DE UM BLOCO VERTICAL PERFEITO:
  PRE-CHECK ZEUS
  ├─ [SKILLS]   → Ler e absorver as Skills da fase mapeadas em (C:/Users/Carlos/.gemini/skills/)
  ├─ [CODE]     → Implementar a feature (lógica e estrutura)
  ├─ [TEST]     → Validar funcionamento (executar pytest)
  ├─ [AUDIT]    → Post-Check ZEUS (Anti-TODO, Anti-Genérico, Prova de Vida)
  ├─ [CHECKLIST]→ Marcar as checkboxes [ ] para [x] no README_DE_IMPLEMENTACAO.md
  ├─ [COMMIT]   → git commit com mensagem semântica (um por bug/fase)
  └─ [HANDOFF]  → Atualizar chat_log_part2.md + handoff.md
  HANDOFF-AUDIT ZEUS
```

> [!IMPORTANT]
> **REGRAS INVIOLÁVEIS DE EXECUÇÃO (Checklists, Testes e Skills):**
> 1. **Carga Exclusiva e Atômica de Skills sob Demanda:** É expressamente proibido carregar ou ler todas as skills de uma vez. O Claude deve carregar e ler a `SKILL.md` específica (mapeada no `CLAUDE.md`) **apenas no momento em que for começar a executar a tarefa correspondente**. Finalizada aquela tarefa, se a próxima exigir outra skill, ele deve ler a nova skill individualmente antes de iniciar a nova tarefa. Os caminhos oficiais locais portáveis das skills são mapeados em `F:\Criando sites pelo pc\Site AgentFlow Studio\.claude\skills\[NOME_DA_SKILL]\SKILL.md`.
> 2. **Auto-Melhoria de Skills (Auto-Reparo):** Se você cometer algum erro de lógica ou sintaxe e identificar que a causa foi uma instrução errada, desatualizada ou incompleta na Skill local, você DEVE interromper a tarefa, abrir a respectiva Skill (ex: `F:\Criando sites pelo pc\Site AgentFlow Studio\.claude\skills\[nome-da-skill]\SKILL.md`) e corrigi-la/melhorá-la imediatamente antes de continuar.
> 3. **Aviso de Correção no Relatório e Memória:** Caso precise realizar a auto-melhoria de qualquer skill local, você DEVE relatar explicitamente isso sob a seção "### 🛠️ Skills Corrigidas/Melhoradas" na sua resposta final de chat, E TAMBÉM registrar essa informação no arquivo de Handoff ativo (`Conversa/handoff.md`) e no Chat Log ativo (`Conversa/chat_log.md`), explicando detalhadamente a skill modificada, o erro original gerado e a correção aplicada.
> 4. **Checklist no Terminal:** É dever absoluto do Claude marcar as checkboxes no arquivo `F:\Criando sites pelo pc\Site AgentFlow Studio\CLAUDE.md` assim que cada sub-tarefa ou etapa for concluída.
> 5. **Testes e Compilação:** Execute a suíte de testes correspondente antes de prosseguir com qualquer handoff ou mudança de bloco. A aprovação dos testes é pré-requisito obrigatório.

**Por que funciona:**
- Cada bloco é atômico: pode ser retomado por outro agente sem perda de contexto.
- O Claude não "inventa" features extras (combate ao Scope Creep nativo).
- O Mestre valida uma entrega de cada vez, mantendo controle total do projeto.

### 📝 Padrão de Handoff Obrigatório entre Sessões

Para garantir continuidade entre sessões do Claude, cada bloco deve registrar no `chat_log.md`:

```markdown
## [DATA] — Handoff Bloco X (FEAT-XXX / COD-001)
**Feito:** [Descrição objetiva do que foi implementado]
**Arquivos criados/modificados:**
  - [caminho/absoluto/arquivo1.tsx]
  - [caminho/absoluto/arquivo2.ts]
**Próximo:** Bloco X+1 ([Nome da próxima feature])
**Observações:** [Edge cases descobertos, decisões tomadas, riscos identificados]
**Skills Corrigidas/Melhoradas:** [Nome da Skill] (caminho): [O que foi corrigido na skill e o erro que ela causou] / "Nenhuma skill precisou de correções."
**Revisões Claude Pro:** [Número de iterações necessárias]
```

### 🏆 ARES Final Validation Gate (Self-Audit do CEO)

Antes de declarar o projeto concluído, execute este checklist de validação final:

```
[ ] Skills de PRODUÇÃO usadas? Nenhuma skill inadequada foi usada?
[ ] Vertical Slicing: Cada bloco entregou UMA feature completa?
[ ] ZEUS 24/7: PRE-CHECK, MID-CHECK, POST-CHECK e HANDOFF em CADA bloco?
[ ] Anti-TODO: Varredura Anti-TODO em cada POST-CHECK retornou ZERO?
[ ] Anti-Botão-Morto: Todos os botões/ações têm função real?
[ ] Prova de Vida: Cada bloco tem evidência de funcionamento (log/output de teste)?
[ ] Handoff: Cada bloco tem handoff no chat_log_part2.md + handoff.md?
[ ] Git Commit: Cada bloco tem commit semântico (fix/feat/perf/chore)?
[ ] pytest: Passa sem erros?
[ ] python -m py_compile: Zero erros de compilação sintática?
[ ] flake8 / mypy check: Zero warnings críticos?
```

### 🚫 Skills Proibidas (Nunca Usar em Projetos de Produção)

| Skill | Por Que Não Usar |
|-------|-----------------|
| `quick-dev-toolkit` | Velocidade > qualidade, gera código descartável |
| Qualquer skill de prototipagem | Protótipo ≠ produção. Cria dívida técnica imediata. |

### 💬 Prova de Vida — Evidência Obrigatória por Bloco

O Claude **não pode** declarar um bloco concluído sem uma das evidências abaixo:

| Tipo de Feature | Prova de Vida Aceita |
|----------------|---------------------|
| Módulo de Lógica | Output de `pytest` mostrando 100% de cobertura/sucesso |
| Endpoint de API / Client | Resposta JSON correta via chamada de mock ou real |
| Execução de CLI | Output de terminal mostrando os logs de execução corretos |
| Performance / Cache | Tempo de resposta ou indicação de cache-hit no log |
| Python Syntax | Output de `python -m py_compile` com "0 errors" |

---

## 🔄 16. Política de Manutenção dos Arquivos Claude (Quando Atualizar o Quê)

> **Regra de Ouro:** Você NÃO precisa atualizar tudo toda vez que for usar o Claude. A maioria dos arquivos é 100% estável entre sessões. Leia a tabela abaixo e atualize APENAS o que mudou.

### 📋 Tabela de Gatilhos de Atualização

| Situação | Arquivos a Atualizar |
|----------|----------------------|
| **Mudou de missão/fase** (ex: acabou os 97 bugs, nova feature) | `CLAUDE.md` + `.claude/commands/task-sync.md` |
| **Chat log avançou de parte** (ex: `chat_log_part7.md` → `part8.md`) | `CLAUDE.md` (linha "Chat Log ativo") + `.claude/commands/task-sync.md` |
| **Novo arquivo de task criado** | `CLAUDE.md` (tabela de arquivos ativos) + `.claude/commands/task-sync.md` |
| **Mudou stack ou portas** (ex: porta 3010 → 3012) | `CLAUDE.md` (seção Stack) + `.claude/settings.json` |
| **Precisa de novas permissões de comando** | `.claude/settings.local.json` |
| **Nova pasta pesada apareceu** (ex: nova `dist/`, `coverage/`) | `.claudeignore` |
| **Mudou de monorepo/repositório** | Todos os arquivos |

---

### ⚡ A Única Coisa que Muda com Frequência

> O **chat_log ativo** é o único arquivo que muda frequentemente (a cada parte nova do histórico).
> Quando avançar de `_part7` para `_part8`, atualize **exatamente 2 lugares**:

```
1. CLAUDE.md                      → linha "Chat Log (parte ativa)"
2. .claude/commands/task-sync.md  → referência ao arquivo chat_log_partX.md
```

Tudo o mais fica estável até mudar de missão ou stack.

---

### 📁 Mapa dos Arquivos Claude e Suas Funções

| Arquivo | Função | Frequência de Atualização |
|---------|--------|--------------------------|
| `CLAUDE.md` | Constituição da sessão: missão, stack, skills, task ativo | Raramente (por mudança de missão) |
| `.claude/settings.json` | Hooks automáticos, excludePatterns | Raramente (por mudança de stack) |
| `.claude/settings.local.json` | Permissões de comandos locais (git, npm, prisma) | Raramente (por nova permissão) |
| `.claude/commands/task-sync.md` | Sincronizador de tarefas e ponteiro do chat_log ativo | A cada novo `chat_log_part*.md` |
| `.claude/commands/api-validate.md` | Pipeline de validação Pytest/lint | Raramente |
| `.claudeignore` | Exclusão de pastas pesadas do contexto | Raramente (nova pasta de build) |
| `.claude/skills/` | Skills de suporte carregadas sob demanda | Nunca (gerenciado pelo setup) |

---

### ✅ Checklist de Início de Sessão (Antes de Rodar `claude`)

Execute mentalmente antes de abrir o terminal:

```
[ ] chat_log ativo está correto no CLAUDE.md?
    → Verifique: "Chat Log (parte ativa): chat_log_part2.md"
    → Se não: atualize CLAUDE.md + task-sync.md

[ ] O task file ativo existe e está atualizado?
    → Verifique: "Manual de Implementação" no CLAUDE.md
    → Se não: corrija o caminho no CLAUDE.md

[ ] Mudou de missão desde a última sessão?
    → Se sim: reescreva a seção "MISSÃO ATUAL" no CLAUDE.md

[ ] Dependências locais instaladas?
    → Execute: pytest tests/ para validar o ambiente
```

---

### 🚫 O Que NUNCA Precisa Atualizar Manualmente

- **`.claude/skills/`** — gerenciado pelo setup inicial, não tocar
- **`.claude/settings.json`** — estável enquanto o stack não mudar
- **`.claudeignore`** — estável enquanto não aparecer nova pasta grande
- **`.claude/commands/api-validate.md`** — estável enquanto usar pytest

---

### 🧠 Protocolo para o @ceo-agent (Antigravity IDE)

Quando o usuário disser **"vou usar o Claude"** ou **"prepara o Claude"** neste projeto, execute **antes de qualquer outra tarefa**:

1. **Leia** `E:/Meus LLMs/CLAUDE.md` para identificar o estado atual
2. **Verifique** qual `chat_log_partX.md` é o ativo (última parte com conteúdo em `Conversa/`)
3. **Compare** o número da parte com o que está registrado em:
   - `CLAUDE.md` → linha "Chat Log (parte ativa)"
   - `.claude/commands/task-sync.md` → referência ao arquivo de log
4. **Se divergirem** → atualize os 2 arquivos com o número correto antes de prosseguir
5. **Verifique** se o task file referenciado no `CLAUDE.md` existe no caminho absoluto indicado
6. **Sincronize e realize o Pruning de Skills locais:** Compare a lista de "Skills Portáveis Ativas" no `CLAUDE.md` com a pasta `C:/Users/Carlos/.gemini/skills/`. Copie qualquer uma das skills ativas ausentes da pasta global para a pasta local se necessário.
7. **Só então** prossiga com a tarefa solicitada
8. **Autonomia nas atualizações do CLAUDE.md:** Quando o usuário solicitar modificações no `CLAUDE.md`, o `@ceo-agent` deve aplicar as atualizações de forma autônoma e memorizada, garantindo que as regras estejam sempre preservadas.
9. **Regra Absoluta de Carregamento de Skills:** Em qualquer atualização do `CLAUDE.md` ou geração de roteiros de tarefas, o `@ceo-agent` DEVE definir como regra imperativa e inviolável para o Claude a obrigação de ler e carregar as Skills locais correspondentes à tarefa antes de rodar ou modificar o código-fonte.
10. **Gerenciamento Autônomo do Headroom:** Ao inicializar a sessão do Claude, o `@ceo-agent` deve verificar silenciosamente se o contêiner `headroom-proxy` está ativo no Docker Desktop e, caso esteja inativo, iniciá-lo de forma autônoma. Além disso, deve garantir o roteamento permanente do proxy configurando a base URL.
11. **Autoconsolidação de Memória de Tokens:** Ao finalizar tarefas críticas ou encerrar a sessão de trabalho, o `@ceo-agent` deve rodar autonomamente o comando `headroom learn --apply` na raiz do projeto.
12. **Garantia de Idioma (PT-BR):** Certifique-se de que todas as comunicações, instruções no `CLAUDE.md` e respostas do Claude para o usuário final sigam estritamente o idioma Português do Brasil (PT-BR).

> **Relatório de Confirmação Obrigatório:**
> Após os passos 1-7, reporte ao usuário:
> `✅ CLAUDE.md OK | chat_log ativo: chat_log | task: CLAUDE.md | Pronto para rodar o AgentFlow Studio`
>
> Adicionalmente, forneça o following prompt otimizado de um clique para o Claude iniciar a execução:
> `Analise o arquivo F:\Criando sites pelo pc\Site AgentFlow Studio\Cria\PRD_AgentFlow_Studio_v1_1.md e a governança em F:\Criando sites pelo pc\Site AgentFlow Studio\CLAUDE.md para iniciar o planejamento e setup do MVP, comunicando-se sempre em Português do Brasil (PT-BR).`


---

## 🐳 17. Otimização e Compressão de Tokens com Headroom AI

O **Headroom AI** está configurado no PC como a camada intermediária de otimização de tokens (compressão reversível de 60% a 95%) para uso no dia a dia com o **Claude Code**.

### ⚙️ 1. Infraestrutura Instalada e Configurações
*   **Serviço Docker (Proxy):** Container `headroom-proxy` ativo na porta `8787`. Configurado sob demanda (`--restart=no`), ou seja, **não** inicia sozinho ao abrir o Docker Desktop para poupar recursos do PC.
*   **Ativação Silenciosa:** Script VBScript [start_headroom.vbs](file:///e:/Meus%20LLMs/Conversa/start_headroom.vbs) configurado para rodar a ativação de forma invisível.
*   **Atalho na Área de Trabalho:** `Ativar Headroom` (ícone de circuito integrado/IA) — dê dois cliques nele para subir o container de forma 100% silenciosa antes de iniciar o Claude.

---

### 💻 2. Como Usar o Headroom no Terminal da IDE

Você não precisa rodar o Claude em uma janela externa. Pode utilizá-lo diretamente no terminal integrado da IDE:

1.  **Dê dois cliques** no atalho `Ativar Headroom` na Área de Trabalho (ou rode `docker start headroom-proxy` no terminal).
2.  **No Terminal da IDE**, configure a variável de ambiente que direciona a API do Claude para o proxy local:
    *   **No PowerShell (padrão da IDE):**
        ```powershell
        $env:ANTHROPIC_BASE_URL='http://localhost:8787/v1'
        ```
    *   **No Git Bash / Linux:**
        ```bash
        export ANTHROPIC_BASE_URL=http://localhost:8787/v1
        ```
3.  **Inicie o Claude Code:**
    ```bash
    claude
    ```
    *Agora, todas as chamadas e tool outputs serão comprimidos em segundo plano pelo container Docker.*

---

### 🌐 3. Uso do Headroom com a API da OpenAI (Aider, Cursor, SDKs)

Além do Claude Code (Anthropic), o **Headroom Proxy** no Docker suporta de forma nativa a interceptação e compressão de chamadas da API da OpenAI. Com base na especificação oficial de referência da API da OpenAI (`developers.openai.com`), qualquer cliente compatível com `/v1` pode usar o proxy na porta `8787`.

#### Como Configurar no Seu Projeto/Terminal:
1.  Garanta que o contêiner `headroom-proxy` está ativo na porta `8787`.
2.  Defina a variável de ambiente de redirecionamento de base URL no seu terminal ou arquivo de configuração:
    *   **No PowerShell (padrão do Windows):**
        ```powershell
        $env:OPENAI_BASE_URL='http://localhost:8787/v1'
        ```
    *   **No Git Bash / Linux:**
        ```bash
        export OPENAI_BASE_URL=http://localhost:8787/v1
        ```
3.  **No Cursor / Cline / Aider / VS Code:** Nas configurações de provedores de IA ou OpenAI, configure a URL base da API como `http://localhost:8787/v1`.
4.  *Os cabeçalhos de autorização (`Authorization: Bearer OPENAI_API_KEY`), tokens de organização (`OpenAI-Organization`) e identificadores de projeto (`OpenAI-Project`) são repassados de forma transparente e segura pelo Headroom, aplicando o SmartCrusher e o CacheAligner automaticamente.*

---

### 🛠️ 4. Roteamento Permanente do Claude (Opcional)

Se você quiser que o Claude Code **sempre** tente usar o proxy da porta 8787 sem que você precise digitar a variável `$env:ANTHROPIC_BASE_URL` a cada novo terminal, rode o hook durável no PowerShell:
```powershell
headroom init claude
```
*Caso o container esteja desligado ao rodar o Claude permanentemente configurado, ele retornará erro de conexão. Lembre-se de sempre ativar o container antes.*

---

### 📋 5. Tabela de Comandos do Dia a Dia

Use estes comandos no terminal para gerenciar o Headroom e auditar sua economia:

| Comando | O que faz | Quando usar? |
| :--- | :--- | :--- |
| `docker start headroom-proxy` | Inicia o contêiner de proxy em background. | Quando for começar a trabalhar e não quiser clicar no atalho do Desktop. |
| `docker stop headroom-proxy` | Desliga o contêiner de proxy. | Ao finalizar o expediente para liberar recursos. |
| `headroom perf` | Exibe o relatório de performance e **quantos tokens você economizou** na sessão atual. | Ao final de uma sessão longa de programação para verificar a taxa de redução de custo. |
| `headroom learn --apply` | Varre os logs locais de falhas de prompts anteriores e compila aprendizados nos arquivos `cloud.md` ou `agents.md`. | Uma vez por semana para retroalimentar a IA com as particularidades do projeto e evitar erros repetidos. |
| `headroom memory list` | Lista os blocos de memória e arquivos indexados no cache local. | Para auditar o que o Headroom está armazenando. |
| `headroom unwrap claude` | Remove os ganchos permanentes e desfaz a integração automática do Claude. | Se precisar voltar a usar o Claude Code direto na API da Anthropic sem o proxy intermediário. |

---