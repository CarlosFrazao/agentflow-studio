# Índice de Execução — Plano de Integração de Inteligência de Agentes

Cada tarefa abaixo é um arquivo **auto-contido**: traz objetivo, origem no
diretório `Hermes\hermes-agent`, destino no AgentFlow, esqueleto de código,
critérios de aceitação e comando de verificação. Um modelo de IA novo pode
executar qualquer arquivo sem ler o resto da conversa.

**Regra rígida comum a todas as tarefas:** nenhum arquivo novo do AgentFlow pode
conter a substring `hermes` (nem em nome, nem em imports, nem em comentários,
nem no corpo de skills geradas).

**Caminhos-base:**
- Hermes (somente leitura): `F:\Criando sites pelo pc\Site AgentFlow Studio\Hermes\hermes-agent\`
- AgentFlow backend: `F:\Criando sites pelo pc\Site AgentFlow Studio\backend\`
- Skills do projeto: `F:\Criando sites pelo pc\Site AgentFlow Studio\.claude\skills\`

---

## Mapa de Fases → Tarefas → Modelo sugerido

| Fase | Arquivo | Tarefa | Sugestão de modelo | Dependências |
|---|---|---|---|---|
| A | `Fase_A1_Skill_Factory.md` | Gerador de habilidades dinâmicas | Sonnet (raciocínio médio) | nenhuma |
| A | `Fase_A2_Error_Classifier_Backoff.md` | Classificação de erros + backoff | Haiku (mecânico/adaptação) | nenhuma |
| B | `Fase_B1_Compressao_Artefatos.md` | Compressão de artefatos entre agentes | Opus/Sonnet (LLM) | nenhuma |
| B | `Fase_B2_Orquestracao_Aprimorada.md` | Orquestração retomável + lições | Sonnet | Fase B1 (opcional) |
| C | `Fase_C1_Metricas_Insights.md` | Motor de métricas p/ Dashboard F-013 | Sonnet | nenhuma |
| D | `Fase_D1_Grafo_Preferencias.md` | Grafo de preferências aprendidas F-010 | Haiku/Sonnet | Fase D2 (compartilham tabela) |
| D | `Fase_D2_Memoria_Aprendizado.md` | Memória de aprendizado incremental | Haiku/Sonnet | nenhuma |

**Ordem recomendada:** A1 → A2 (base) → B1 → B2 → C1 → D1/D2 (D em paralelo).

**Antes de qualquer tarefa**, o modelo executor deve ler:
1. `Cria\PRD_AgentFlow_Studio_v1_1.md` (escopo das features)
2. `Cria\Spec_Tecnica_Integracao_v1_0.md` (endpoints SRA/Firecrawl, circuit breaker)
3. Os arquivos do backend já existentes citados na tarefa.

**Ao terminar cada tarefa:** rodar `pytest` no backend e atualizar
`Conversa\handoff.md` com o que foi feito.
