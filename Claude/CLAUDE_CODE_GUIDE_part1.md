# 📖 Guia Supremo do Claude Code: Comandos e Economia de Tokens

Este guia foi criado para ajudar você a utilizar o **Claude Code CLI** (comando `claude`) com o máximo de eficiência operacional, inteligência e economia de tokens, aproveitando as melhores estratégias e configurações práticas do ecossistema de Vibe Coding.

---

## ⚙️ 1. Otimização Automática e Funcionamento de Tokens

O Claude Code opera sob o modelo de **Prompt Caching**. Toda vez que você envia uma mensagem, o histórico inteiro da conversa é reenviado. 

*   **Cache Hits (Leitura):** Partes idênticas da conversa que já foram enviadas são lidas do cache e cobradas a apenas **10% do custo padrão**.
*   **Cache Misses (Escrita):** Novas alterações ou quando o cache expira (após **5 minutos de inatividade**) são cobradas com acréscimo de **25% de tarifa (1.25x)** para registrar o novo cache.
*   **Ação Recomendada:** Evite fazer pausas longas de mais de 5 minutos durante a execução de uma tarefa focada para não perder o cache ativo.
*   **Combate ao Context Rot (Filosofia GSD):** Para evitar que a IA sofra de "degradação de contexto" (esquecer trechos de código, misturar versões ou ignorar instruções passadas), o **Meus LLMs** adota o método de **Spec-Driven Development (SDD)**. Toda a memória de longo prazo, especificações e tarefas de desenvolvimento estão mapeados em arquivos atômicos separados na pasta [Conversa/](file:///E:/Meus%20LLMs/Conversa/). Isso simula perfeitamente o framework **GSD (Get Shit Done)** nativamente, mantendo a consistência do código sem a lentidão ou burocracia do console GSD.
*   **O Filtro Combinado do `.claudeignore` + `settings.json`:** Criamos um arquivo [`.claudeignore`](file:///E:/Meus%20LLMs/.claudeignore) na raiz do projeto para isolar pastas pesadas como `node_modules`, `.venv`, `__pycache__`, logs e binários. Para máxima eficácia física, combinamos essas regras no arquivo de configurações locais do Claude (`.claude/settings.json`) sob a chave `excludePatterns`, impedindo a IA de varrer código morto ou gastar tokens indexando caches.

### 💻 Ambientes de Execução do Claude Code
Você pode rodar o Claude em quatro ecossistemas principais:
1.  **Terminal CLI Local (`claude`):** O ambiente mais rápido e o primeiro a receber novos updates e comandos avançados via `claude update`.
2.  **Claude Desktop App:** A interface de aplicativo dedicada para o seu sistema operacional.
3.  **VS Code Extension ("Claude Code for VS Code"):** Extensão oficial para integrar a IA direto no editor de código.
4.  **Interface Web:** Acesso direto via navegador (geralmente limitado por exigir sincronização via GitHub).
*   *Recomendação para o Meus LLMs:* Use sempre o **Terminal CLI Local** para aproveitar 100% dos slash commands customizados e scripts nativos em background.

---

## ⌨️ 2. Comandos Interativos (Slash Commands)

Estes comandos são digitados diretamente dentro do prompt interativo do Claude (`claude`):

### 💎 Economia de Tokens e Limpeza
| Comando | O que faz | Quando usar? |
| :--- | :--- | :--- |
| `/btw [pergunta]` | Executa uma pergunta paralela (side question) abrindo uma subvisualização. Responde usando cache, sem salvar a pergunta no histórico e sem rodar tools. | **Sempre.** Use para tirar dúvidas de arquitetura, perguntar o porquê de uma abordagem ou tirar dúvidas pontuais sem poluir o histórico nem gastar tokens. |
| `/compact` | Resume o histórico de conversas da sessão atual e remove trechos de código antigos da memória. | **Sempre.** Use a cada 10 a 15 interações para resetar o peso de tokens acumulados na conversa. |
| `/clear` | Limpa toda a conversa da sessão atual e inicia um histórico zerado. | **Ao mudar de tarefa (Recomendação Anthropic).** Evite misturar tarefas (ex: ir do frontend para o backend) na mesma sessão. Use `/clear` para ter um contexto 100% limpo e poupar tokens arrastados de etapas concluídas. |
| `/dream` (Autodream) | Entra em estado de "Sonho" (Dreaming) para consolidar a memória. Lê, poda dados obsoletos ou duplicados e compacta a memória a < 200 linhas. | **Automaticamente.** Roda a cada 24h ou 5 sessões se ativado em `/config` -> `memory` -> `Autodream` = `ON`. Pode ser forçado digitando: *"Perform a dream, consolidate and reorganize my memory files."* |
| `/context` | Exibe graficamente o uso do contexto da janela (tokens usados pela conversa, ferramentas e sistema). | Use para monitorar quando o histórico de mensagens está ficando pesado demais e precisa de um `/compact`. |
| `/usage` | Exibe o relatório de tokens de entrada/saída consumidos e a estimativa de custo da sessão ativa. | Use para auditar seus gastos e entender quais prompts estão consumindo mais recursos. |

### 🛠️ Configuração e Ajustes
| Comando | O que faz | Quando usar? |
| :--- | :--- | :--- |
| `/status` | Exibe um painel completo com o estado operacional da sessão (nome da sessão ativa, plano, modelo ativo, uso de tokens da cota, MCPs ativos e configurações). | Use para monitorar o seu consumo físico da cota da Anthropic em tempo real sem precisar ir ao navegador. |
| `/init` | Analisa a fundo o projeto inteiro de forma global e gera ou atualiza o arquivo de governança principal `CLAUDE.md`. | **Na inicialização ou migração de fase.** Use para polir e blindar o `CLAUDE.md` com base na evolução recente da base de código. |
| `/effort [low\|medium\|high\|max]` | Altera o nível de raciocínio profundo (thinking budget) do modelo ativo. | **Low:** Tarefas mecânicas simples. **Medium (Ideal):** Desenvolvimento diário padrão. **High:** Regras e algoritmos difíceis. **Max:** Planejamento arquitetural pesado de novos módulos. |
| `/model [sonnet\|haiku\|opus]` | Alterna o modelo de linguagem utilizado na sessão atual. | Use modelos menores como **Haiku** para tarefas rápidas de terminal/refatorações simples e **Sonnet** ou **Opus** para lógica avançada de backend. |
| `/mcp` | Lista, adiciona e gerencia os servidores de plugins do Model Context Protocol (MCP). | Use para monitorar e remover ferramentas desnecessárias que possam estar poluindo o tamanho básico de cada prompt enviado. |
| `/config` | Abre o menu de configurações interativo do Claude Code. | Use para configurar preferências visuais, editores padrões e comportamento de escrita. |

### 🔬 Comandos de Auditoria e Background (Avançado)
*   **`/simplify` (Auditoria & Refatoração Paralela):**
    *   *O que faz:* Dispara simultaneamente três subagentes dedicados para revisar o código alterado sob as óticas de **Eficiência (Performance)**, **Legibilidade (Clean Code)** e **Duplicação (Reutilização)**.
    *   *Uso:* Execute `/simplify` sempre após finalizar a implementação de um novo controlador, serviço ou rota crítica para garantir blindagem técnica e refatoração de alta qualidade.
*   **`/loop [tempo] "[prompt]"` (Agendamento de Tarefas / Cron Jobs):**
    *   *O que faz:* Permite agendar uma tarefa local para rodar em background no terminal periodicamente por até 3 dias (ex: `loop 30m "verifique se há alterações locais e faça um git commit descritivo baseando-se no diff"`).
    *   *Uso:* Ideal para automatizar logs, rodar suites de testes em background, ou garantir backups regulares enquanto você foca na digitação do código principal.
*   **`/go [prompt]` (Execução Autônoma Ininterrupta):**
    *   *O que faz:* Agenda e dispara um agente autônomo concorrente que trabalha e se autocorrige ininterruptamente até atingir um critério de parada específico sem necessidade de supervisão humana constante.
    *   *Uso:* Excelente para rodar diagnósticos profundos de segurança, refatorações pesadas, e correções automáticas de falhas de testes e compilação em background.

---

## ⌨️ 3. Atalhos de Teclado e Truques de Terminal

Atalhos rápidos para economizar tempo e tokens sem digitar comandos longos:

### ⚡ Atalhos Rápidos
*   **`Alt + T`** (Windows/Linux) ou **`Option + T`** (macOS):
    *   **Função:** Liga ou desliga instantaneamente o modo **Thinking (Raciocínio)**.
    *   **Uso:** Desligue para perguntas diretas, comandos simples de terminal ou automações para economizar 100% dos tokens de pensamento.
*   **`Shift + Tab`**:
    *   **Função:** Alterna instantaneamente entre o modo de execução (**Accept Edits ON**) e o modo de planejamento (**Plan Mode**).
    *   **Uso:** Alterne para planejar sua feature graficamente em pseudo-código e volte para implementar as alterações físicas com velocidade.
*   **`Ctrl + C`**:
    *   **Função:** Interrompe a geração da resposta atual do Claude.
    *   **Uso:** Se você perceber que ele começou a gerar uma resposta errada ou longa demais, interrompa imediatamente para economizar tokens de saída.

### 🎯 A Mira Telescópica: Referência de Arquivos com `@`
*   **Como usar:** Digite o caractere `@` seguido do nome do arquivo no prompt (ex: `@apps/api/src/app.module.ts verifique se a rota está importada`).
*   **Vantagem:** Isso cria um foco cirúrgico (sniper target) no arquivo mencionado. O Claude lerá estritamente o arquivo referenciado, economizando milhares de tokens que seriam gastos varrendo a árvore de diretórios à procura de referências.

### ⛓️ Enfileiramento de Prompts (Prompt Queuing)
*   **Como usar:** Você pode digitar e submeter prompts adicionais no console do Claude enquanto ele ainda está respondendo a uma instrução anterior.
*   **Vantagem:** O terminal cria uma fila em background de comandos subsequentes. Você pode inclusive pressionar a **seta para cima** para editar a fila antes dela rodar. Use para corrigir o curso do Claude no meio da geração de um código ou encadear correções rápidas de testes, economizando tempo e evitando refazer prompts do zero.

### 🔌 O Truque do Prefixo de Exclamação `!`
*   **Como usar:** Digite `!` seguido de qualquer comando de shell diretamente no console do Claude (ex: `!npm run dev`, `!git status`, `!tsc --noEmit`).
*   **Por que economiza tokens:** A exclamação faz com que o Claude execute o comando diretamente no terminal local do sistema operacional **sem passar pela LLM**. Isso significa que ele não precisa ler o comando, planejar a execução ou consumir tokens de entrada/pensamento. Use sempre que souber exatamente o comando que deseja rodar!

---

## 🎛️ 4. Parâmetros de Inicialização (Flags de Terminal)

Comandos para executar ao chamar o Claude pelo terminal do Windows (`cmd` ou `PowerShell`):

### 💸 Limites de Segurança
*   `claude --thinking-budget <tokens>`
    *   *Exemplo:* `claude --thinking-budget 1024`
    *   *Uso:* Define o limite máximo de tokens que o Claude pode usar para "pensar" em cada resposta. Evita loops caros de raciocínio.
*   `claude --token-budget <tokens>`
    *   *Exemplo:* `claude --token-budget 80000`
    *   *Uso:* Limite absoluto de tokens para a sessão. O Claude salva o progresso e encerra se o limite for atingido, prevenindo faturas indesejadas.

### 🚀 Atalhos de Sessão
*   `claude -c` (ou `claude --continue`)
    *   *Uso:* Continua a última conversa salva no mesmo estado, aproveitando o cache de arquivos se estiver dentro da janela de 5 minutos.
*   `claude -p "sua pergunta"`
    *   *Uso:* Executa a instrução, exibe o resultado diretamente na tela e **fecha a sessão na hora**. Não deixa o console aberto. Ideal para automações super rápidas e econômicas.
*   `claude doctor`
    *   *Uso:* Diagnostica a integridade do Claude Code e a comunicação com a API da Anthropic.

---

## 🔌 5. Servidores MCP (Plugins) de Alta Eficiência

Os plugins no Claude Code expandem o conhecimento do modelo por meio do protocolo MCP.

1.  **Context7 MCP** (`claude mcp add context7 -- npx -y @upstash/context-mcp@latest`):
    *   *Objetivo:* Resolve de forma definitiva o problema de **conhecimento obsoleto de bibliotecas (Next.js 14/15, Prisma v6/v7, React 19)**. Ele se conecta à API do Context7 da Upstash e busca documentações atualizadas em tempo real sob demanda a cada prompt.
    *   *Uso:* Invoque adicionando no prompt: *"... use o context7 para validar se a sintaxe do Next.js está correta."*
2.  **Sequential Thinking MCP** (`claude mcp add @modelcontextprotocol/server-sequential-thinking`):
    *   *Objetivo:* Guia o Claude por um raciocínio sequencial estruturado. Isso faz com que ele resolva problemas complexos de primeira, sem gastar tokens errando e tentando novamente.
3.  **PostgreSQL MCP**:
    *   *Objetivo:* Permite consultas diretas a schemas e tabelas. Evita que você precise expor arquivos SQL gigantescos na conversa.
4.  **GitHub MCP**:
    *   *Objetivo:* Permite ler issues, branches e pull requests diretamente do console.

---

## 🛠️ 6. Comandos Customizados do Projeto (Custom Slash Commands)

Estes comandos foram criados sob medida para o projeto **Meus LLMs** e estão salvos na pasta `.claude/commands/`. Eles ajudam a automatizar tarefas recurrentes do Claude CLI economizando até 90% de tokens:

### 🚀 `/api-validate`
*   **O que faz:** Executa de forma combinada e automatizada as validações de sintaxe de arquivos Python modificados (`python -m py_compile`), verificação Anti-TODO e execução dos testes unitários com `pytest` filtrando os logs de sucesso para economizar tokens.
*   **Como usar:** Basta digitar `/api-validate` no console interativo do Claude.

### 🔄 `/task-sync`
*   **O que faz:** Varre os arquivos de tarefas na pasta `./Conversa/` (ex: `README_DE_IMPLEMENTACAO.md`), identifica o progresso das tarefas concluídas e marca automaticamente as checkboxes `[ ]` como `[x]`, além de gerar um relatório rápido de status.
*   **Como usar:** Basta digitar `/task-sync` no console interativo do Claude.

---

## 🖼️ 7. Planejamento Avançado com Ultra Plan

O **Ultra Plan** é um recurso visual e interativo do Claude Code que eleva o planejamento técnico para uma interface web rica, permitindo iterar designs complexos de forma gráfica e colaborativa:

*   **Como ativar:** Digite `/ultraplan [sua feature]` (ou chame via terminal com `claude ultraplan "[sua feature]"`). Ele gerará um link web exclusivo para você abrir no navegador.
*   **A Interface Web:** Na aba do navegador, você verá o plano ultra detalhado das alterações, permitindo adicionar comentários inline em trechos do plano, reagir com emojis, navegar pelas outlines laterais e iterar revisões antes de aprovar.
*   **Retorno e Execução:** Ao aprovar o plano na web, ele é mandado de volta para o terminal local do Claude. Você pode optar por implementar na hora, salvar em um arquivo ou abrir um pull request no GitHub.
*   **Quando USAR:** Em tarefas de alta criticidade e complexidade que envolvam mais de 5 arquivos, grandes migrações de bancos (ex: adicionar tabelas e relações no Prisma), refatorações de arquitetura crítica do NestJS, ou features com muitas dependências cruzadas (ex: tracking de GPS no WebSocket ou integração assíncrona do BullMQ).
*   **Quando IGNORAR:** Em tarefas mecânicas ou triviais de rotina (bugs de CSS, adição de um campo simples na tabela, criação de DTOs simples). Use o planejamento local básico do terminal nestes casos para economizar tokens de API e tempo de processamento.

---

## 🪓 8. Boas Práticas de Envio de Logs e Debugging

Estratégias para otimizar os prompts manuais enviados e manter o contexto ultra leve:

1.  **Não colar logs gigantes:**
    *   *O problema:* Colar uma stack trace inteira do Next.js ou Node.js (com mais de 100 linhas de arquivos internos das bibliotecas) polui o prompt e infla enormemente o custo.
    *   *A solução:* Envie apenas o topo do erro (a mensagem principal) e a linha exata em que o erro aconteceu no seu código (geralmente as primeiras 5 a 10 linhas). O Claude não precisa de todas as chamadas de bibliotecas internas do node para entender a origem do problema.
2.  **Desconectar MCPs Globais e Inativos:**
    *   *O problema:* Cada servidor MCP globalmente instalado injeta todas as suas ferramentas e esquemas no contexto de **toda e qualquer mensagem** enviada, mesmo que não seja usada.
    *   *A solução:* Comece com o mínimo de plugins globais. Digite `/mcp` para verificar quais servidores estão ativos e remova ou desative temporariamente os que forem irrelevantes para a tarefa ativa. Se possível, configure MCPs apenas locais/por projeto.
3.  **O Plugin `context-mode` (Opcional/Avançado):**
    *   *O que é:* O plugin de terceiros `context-mode` (da comunidade, disponível em `github.com/mksglu/context-mode`) gerencia e compacta de forma automatizada o histórico de conversas do Claude Code mantendo trechos chaves em um banco de dados SQLite local.
    *   *Nota no Meus LLMs:* Nossa arquitetura atômica em [Conversa/](file:///E:/Meus%20LLMs/Conversa/) combinada com a gestão de `chat_log_part*.md`, `handoff.md` e a regra do `/clear` já atua como uma solução nativa de gerenciamento de memória (nossa própria SSD de contexto), permitindo resetar o chat a qualquer momento com risco zero de esquecimento.

---

## 🗿 9. A Estratégia Caveman (Output Ultra Enxuto)

O **Caveman** (`github.com/JuliusBrussee/caveman`) é um repositório e skill open-source desenhado especificamente para combater o consumo agressivo de tokens de saída (output tokens) do Claude Code CLI.

### 💡 Filosofia de Funcionamento
O Claude costuma gerar longas introduções, explicações repetitivas de processos lógicos e mensagens de cortesia amigáveis. O Caveman injeta um prompt estruturado de sistema que força o Claude a responder no estilo **"homem das cavernas"**: extremamente conciso, ultra resumido e puramente técnico.
*   **Economia Comprovada:** Reduz as respostas do modelo em até **75%**, gerando retornos até **3x mais rápidos** sem comprometer a exatidão.
*   **Preservação Total:** Ele **não altera** o código gerado, blocos de raciocínio lógico (thinking), URLs, comandos de shell, tabelas ou mensagens de erro nativas. Ele limpa estritamente a "falação vazia".

### 🛠️ Como Instalar e Usar no Console
1.  **Instalação Global:**
    `npx skills add caveman` (selecione a instalação global ou local por projeto)
2.  **Níveis de Intensidade:**
    *   `caveman light`: Respostas levemente enxutas, mantendo fluidez.
    *   `caveman full`: Direto ao ponto, remove fillers e preposições extras.
    *   `caveman ultra`: Redução máxima, responde estritamente no jargão técnico (ex: *"FN recursiva chama-se mesma bate base sem stack overflow"*).
    *   `caveman winyan`: Converte explicações secundárias em caracteres de chinês clássico (redução física máxima de caracteres), mas mantém o código e os comandos em inglês.

### ⚡ Truque: Caveman Sem Instalação (System Prompt Local)
Se você não deseja instalar a dependência global, você pode alcançar o mesmo resultado incluindo a instrução abaixo no seu prompt de sistema ou ao iniciar o chat:
> *"Responda utilizando o estilo Caveman Ultra: elimine rodeios, artigos e explicações redundantes. Mantenha 100% de foco no código técnico e seja extremamente bruto e direto nas microexplicações textuais."*

---

## 🏆 10. O Framework Gstack (Vibe Coding de Elite)

O **Gstack** (`github.com/garrytan/gstack`) é um framework de metaprompts de alto nível criado por Garry Tan (CEO da Y Combinator). Ele foca na viabilidade de startups e engenharia sólida, combatendo a "programação assistida desleixada" (vibe coding sem rigor e cheia de vulnerabilidades).

### 💡 Fases de Desenvolvimento e Comandos Chave
O Gstack opera o ciclo de vida de uma aplicação dividindo o Claude em papéis técnicos e de negócios muito nítidos:
1.  **`office hours` (Alinhamento & Ideação):** Fase de debate inicial de produto, desafiando nicho, valor comercial e viabilidade da ideia.
2.  **`plan` (Planejamento Multidisciplinar):** O Claude assume três subrevisores específicos antes da codificação:
    *   `CEO review`: Desafia a retenção do produto, simplicidade e conversão.
    *   `Eng review`: Define a arquitetura técnica de dados, schemas e infraestrutura.
    *   `Design review`: Gera wireframes em HTML cru direto no console para testar e aprovar a experiência visual do usuário.
3.  **`build` (Construção Linear):** O Claude inicia o desenvolvimento puramente estruturado com base nos acordos das fases de review.
4.  **`review` / `qa` / `cso` (Fase de Validação Rigorosa):**
    *   `review`: Analisa minuciosamente commits e PRs locais em busca de inconsistências de arquitetura.
    *   `qa`: Executa testes automatizados de fluxo e browser em busca de rotas quebradas.
    *   `cso` (Chief Security Officer): Revisor de segurança focado em brechas críticas (vazamento de chaves, queries SQL inseguras, escalação de privilégios e rotas de API desprotegidas).
5.  **`reflect` (Retrospectiva):** Consolida feedbacks do ciclo de build e documenta as falhas para que a IA se vacine no próximo ciclo.

### ⚡ Como Invocar Esses Papéis Nativamente (Vibe Coding Avançado)
Mesmo sem instalar o Gstack fisicamente via repositório, você pode extrair o máximo do seu potencial invocando essas metodologias nos seus prompts nativos com o Claude:
*   **Para Segurança (CSO):** *"Assuma a postura de Chief Security Officer (CSO) e audite este controlador de banco de dados/autenticação em busca de falhas OWASP, vazamentos e injeções. Retorne em formato de relatório de criticidade antes de corrigir."*
*   **Para Negócio (CEO):** *"Faça um CEO review do fluxo de compra. Onde estão os atritos visuais e funcionais? Proponha simplificações de UX."*
*   **Para Arquitetura (Eng):** *"Faça um Eng review. Avalie a modularidade desse serviço NestJS, os gargalos de concorrência e a consistência transacional sob grande concorrência."*

---

## 🚀 11. Governança Avançada, Subagentes e Hooks Customizados

Esta seção traz recursos profundos de customização do Claude Code CLI no nível do projeto, automatizando regras operacionais de vibe coding de forma imperativa:

### 💾 1. O Recurso de Memória Persistente (`#memory`)
Diferente do `CLAUDE.md` (que serve para dados estruturados rápidos e arquitetura), você pode alimentar a memória permanente do Claude com suas preferências e padrões de escrita.
*   **Como usar:** Insira `#memory` seguido da instrução no seu prompt (ex: `#memory adicione a regra de que todas as funções devem ser devidamente comentadas com JSDoc`).
*   **Onde é salvo:** O Claude salva essas preferências na raiz do seu diretório local sob a pasta `.claude/memory.json`. A IA lerá essa memória em todas as futuras conversas para manter o padrão sem que você precise re-escrever.

### 🤖 2. Subagentes Customizados
Você pode programar o Claude para disparar subagentes altamente especializados em tarefas em paralelo.
*   **Como criar:** Salve um arquivo markdown com as instruções do subagente na pasta `.claude/agents/` (ex: `tester.md`).
*   **Exemplo de Prompt de Agente (`.claude/agents/tester.md`):**
    > *"Você é o Tester Agent, especialista em criar testes automatizados utilizando Jest e Playwright. Você tem permissões de leitura, escrita e bash. Para cada código TypeScript fornecido, escreva suítes de teste de caminhos felizes e edge cases."*
*   **Como invocar:** Digite na conversa interativa: *"Invoque o subagente tester para cobrir de testes o arquivo @app.service.ts"*. O Claude rodará o agente de forma concorrente em background!

### ⚓ 3. Hooks TypeScript e Builds Automatizados
Você pode registrar "Hooks" de eventos no arquivo de configuração do projeto (`.claude/settings.json`) para automatizar validações físicas após cada alteração do Claude.

> [!IMPORTANT]
> **Compatibilidade de Versão (Claude Code v2):** O Claude v2 não aceita mais hooks declarados de forma simples como `"post-edit": "comando"`. Fazer isso causará o aviso `Settings Warning / 1 setup issue`. Os hooks agora devem seguir a estrutura de arrays com matchers.

*   **Como configurar:** No `.claude/settings.json`, adicione chaves de gatilhos estruturados.
*   **Exemplo Prático e Correto (PostToolUse pós-alteração):**
    ```json
    {
      "hooks": {
        "PostToolUse": [
          {
            "matcher": "Edit|Write",
            "hooks": [
              {
                "type": "command",
                "command": "npx tsc --noEmit"
              }
            ]
          }
        ]
      }
    }
    ```
    *Isso força o Claude a testar a transpilação TypeScript do projeto a cada arquivo de código que ele modificar usando as ferramentas Edit ou Write. Se a compilação falhar, o Claude detecta o erro e autocorrige a sintaxe imediatamente antes de entregar a resposta final.*

---

## 📚 12. Otimização de Bibliotecas com Context7 (MCP vs. Skill Wizard)

O **Context7** da Upstash (`github.com/upstash/context7`) é uma ferramenta fantástica de Vibe Coding. Ele resolve o principal causador de erros e desperdício de tokens de depuração: **conhecimento obsoleto de bibliotecas que atualizam rapidamente (ex: Next.js 14/15, Prisma v6/v7, React 19)**, mantendo a IA sempre integrada com a documentação oficial mais recente.

Você pode adotá-lo de duas formas estratégicas no projeto **Meus LLMs**:

### 🔌 Método A: O Servidor MCP Dinâmico (Consulta em Tempo Real)
*   **Como instalar:** Digite `claude mcp add context7 -- npx -y @upstash/context-mcp@latest` no terminal do Claude.
*   **Funcionamento:** Quando ativado, o Claude consulta em tempo real a documentação via API da Upstash sob demanda nas suas mensagens.
*   *Prós:* 100% dinâmico e sempre na última versão.
*   *Contras:* Cada chamada adiciona tráfego de rede e overhead básico de tokens ao contexto do chat. Recomendado para dúvidas rápidas e explorações isoladas de pacotes desconhecidos.

### 🧙‍♂️ Método B: O Skill Wizard Local (Recomendado - Sem Consumo de Tokens)
*   **Como usar:** Rode no terminal do sistema: `npx @upstash/context7 skills generate` (ou utilize o atalho de CLI `npx ctx7 skills generate`).
*   **Funcionamento:** O assistente do Context7 solicitará login, analisará as tecnologias do seu diretório e fará perguntas sobre a expertise que você deseja encapsular (ex: Python 3.11, pytest, aiohttp). Ele então criará um arquivo Markdown de especificação estática super enxuta e otimizada sob o diretório `.claude/skills/`.
*   **Como invocar no prompt:** Peça expressamente na mensagem:
    > *"Utilizando a skill local python-clean-code, implemente o searcher..."*
*   *Prós:* **Extrema economia de tokens**, execução offline ultra rápida e sem latência de rede. A IA lê diretamente as boas práticas estruturadas locais. Recomendado para o desenvolvimento principal de componentes no Meus LLMs.

---

## 🎓 13. O Rigor Karpathy (Código Mínimo e Zero Assunções)

O **Rigor Karpathy** (`github.com/multica-ai/andrej-karpathy-skills`) é uma skill open-source inspirada na disciplina de desenvolvimento de Andrej Karpathy (ex-Diretor de IA na Tesla e cofundador da OpenAI). Seu principal objetivo é extinguir o código "inchado" de IA, evitando que ela crie novas complexidades desnecessárias ou quebre regras preexistentes.

### 💡 Os Quatro Pilares do Rigor Karpathy
A skill instrui e blinda o Claude a respeitar estritamente quatro disciplinas fundamentais:
1.  **Código Mínimo e Cirúrgico (Minimal Code changes):** Reduz drasticamente a quantidade de linhas alteradas e arquivos tocados. A IA altera o mínimo de código físico elegante para resolver a tarefa, combatendo o inchaço (*over-engineering*).
2.  **Zero Assunções Silenciosas (Zero Silent Assumptions):** A IA é estritamente proibida de "adivinhar" o que fazer em prompts vagos. Se houver múltiplos tradeoffs ou decisões críticas (ex: escolha de bibliotecas de autenticação), ela é obrigada a **parar a execução e perguntar ao desenvolvedor** antes de codificar.
3.  **Definição Prévia de Critérios de Sucesso:** A IA estabelece uma mini lista de verificação lógica de como testar a nova feature antes de digitar o código físico, garantindo que o critério de sucesso do diff seja verificado na entrega.
4.  **Combate ao Scope Creep:** A IA foca cirurgicamente nas diretrizes do prompt. Ela nunca mexe ou refatora arquivos adjacentes sem autorização prévia, mantendo o diff do Git extremamente limpo e robusto.

### 🛠️ Como Instalar e Ativar no CLI
1.  **Instalar via Plugins:**
    No terminal do Claude Code, rode:
    `npx skills add plugin-marketplace` e adicione a skill `andrej-karpathy-skills` para o projeto ou de forma global.
2.  **Recarregar plugins:**
    Digite `reload plugins` no terminal do Claude ou reinicie a sessão para ativá-lo.

### ⚡ Truque: Emulação de Prompt Local (Sem Instalação)
Se você não deseja instalar pacotes externos no terminal do Windows, você pode obter 100% da eficácia do Rigor Karpathy incluindo a seguinte instrução no seu prompt de sistema ou na conversa ativa:
> *"Adote a Filosofia Karpathy de Vibe Coding:
> 1. Código Mínimo: Faça modificações cirúrgicas e ultra-elegantes. Nunca adicione novos arquivos ou bibliotecas desnecessárias.
> 2. Zero Assunções Silenciosas: Em caso de ambiguidade ou decisões de arquitetura de múltiplos caminhos, PARE imediatamente e me pergunte os tradeoffs antes de escrever código.
> 3. Critérios de Sucesso: Defina as premissas de teste lógico de entrega antes de iniciar a alteração física.
> 4. Evite Scope Creep: Mantenha as modificações presas estritamente ao escopo da tarefa."*

---

## 🤖 14. O Comando /go (Desenvolvimento Autônomo Ininterrupto)

O comando `/go` (ou simplesmente `go` precedido do prompt no console interativo do Claude) é uma das funcionalidades mais avançadas do Claude Code. Ele permite despachar o Claude em **tarefas totalmente autônomas** em background de longa duração que não exigem a sua supervisão constante.

### 💡 Estrutura de um Bom Prompt de `/go`
Para o Go trabalhar com alta precisão, o seu prompt deve especificar claramente três coisas:
1.  **O objetivo/tarefa:** O que ele deve fazer.
2.  **Definition of Done (DoD):** Qual é o estado final mensurável desejado.
3.  **Comprovação / Critério de parada:** Como ele prova fisicamente para você que atingiu o objetivo para poder parar e encerrar o agente (ex: *"crie o arquivo security.md com as considerações para finalizar"* ou *"conserto de testes: pare assim que rodar `npm test` e obtiver 100% de sucesso nos arquivos alterados"*).

*Exemplo Prático de Prompt:*
> `/go faça uma auditoria profunda de segurança em todas as APIs de pagamento, identificando e corrigindo vulnerabilidades ativamente. Crie o arquivo security.md com os pareceres das correções para encerrar o agente.`

### 🛠️ Subcomandos de Gerenciamento do Go
*   `go` (ou `/go` sem argumentos): Exibe todos os processos de Go ativos no momento e seus estados.
*   `go pause`: Pausa a execução. Ele **não para instantaneamente**, mas termina a micro-iteração ou alteração atual do arquivo antes de pausar, garantindo que o código não fique inconsistente ou quebrado no meio de uma alteração física.
*   `go resume`: Retoma o agente autônomo pausado a partir do ponto em que parou.
*   `go clear`: Aborta, limpa e cancela a fila de iteração do Go ativo de forma imediata.
*   `go complete`: Força a finalização com sucesso da tarefa caso você perceba visualmente que ele já atingiu o objetivo ideal e continuaria rodando iterações redundantes de validação.

### 👥 Rodando Agentes Paralelos Concorrentes (`cloud agents`)
O Claude permite disparar múltiplos goals em paralelo que trabalham de forma concorrente no projeto em background enquanto você apenas supervisiona a fila gráfica de status (ex: disparar um `/go` para performance e um `/go` para segurança simultaneamente no console). O Claude Code orquestra essas sub-threads de forma simultânea e consistente!

---
