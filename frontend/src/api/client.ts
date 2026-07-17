import type { Card, CardMeta, KanbanColumn, PaginatedCards } from "../types/card";
import { getToken, getRefreshToken, refreshAccessToken, clearToken } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

const SESSION_EXPIRED_EVENT = "af:session-expired";

/** Dispara o evento de sessão expirada (ouvido por App/ErrorBoundary p/ toast + login). */
export function emitSessionExpired(): void {
  clearToken();
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
}

export function onSessionExpired(cb: () => void): void {
  window.addEventListener(SESSION_EXPIRED_EVENT, cb);
}

/* ---------- auth-aware fetch com interceptor de 401 + refresh ---------- */
// Em runtime o access token fica em localStorage; o refresh token fica em
// memória (ver auth.ts). Sem token, a API responde 401.
async function apiFetch(path: string, opts: RequestInit = {}): Promise<unknown> {
  return apiFetchOnce(path, opts, false);
}

async function apiFetchOnce(
  path: string,
  opts: RequestInit,
  retried: boolean,
): Promise<unknown> {
  const headers = new Headers(opts.headers);
  headers.set("Accept", "application/json");
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (opts.body) headers.set("Content-Type", "application/json");
  const resp = await fetch(`${API_BASE}${path}`, { ...opts, headers });

  if (resp.status === 401 && !retried && getRefreshToken()) {
    // Tenta renovar o access token uma única vez e refaz a request.
    const renewed = await refreshAccessToken();
    if (renewed) {
      return apiFetchOnce(path, opts, true);
    }
    // Refresh falhou: sessão morta de verdade.
    emitSessionExpired();
    throw new Error("HTTP 401");
  }

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function apiGet<T>(path: string): Promise<T> {
  return (await apiFetch(path)) as T;
}
export async function apiSend<T>(
  method: string,
  path: string,
  payload?: unknown,
): Promise<T> {
  return (await apiFetch(path, {
    method,
    body: payload ? JSON.stringify(payload) : undefined,
  })) as T;
}

/* ---------- cards ---------- */
export async function listCards(params: {
  projectId?: string;
  column?: KanbanColumn;
}): Promise<Card[]> {
  const qs = new URLSearchParams();
  if (params.projectId) qs.set("project_id", params.projectId);
  if (params.column) qs.set("column", params.column);
  const data = await apiGet<PaginatedCards>(
    `/cards?${qs.toString()}&per_page=100`,
  );
  return data.data;
}

export interface Envelope<T> {
  success: boolean;
  data: T;
}

export async function createCard(input: {
  project_id: string;
  title: string;
  column: KanbanColumn;
  meta?: CardMeta;
}): Promise<Card> {
  const r = await apiSend<Envelope<Card>>("POST", "/cards", input);
  return r.data;
}

export async function updateCard(
  id: string,
  patch: Partial<{
    title: string;
    column: KanbanColumn;
    meta: CardMeta;
  }>,
): Promise<Card> {
  const r = await apiSend<Envelope<Card>>("PATCH", `/cards/${id}`, patch);
  return r.data;
}

export async function deleteCard(id: string): Promise<void> {
  await apiFetch(`/cards/${id}`, { method: "DELETE" });
}

export async function moveCard(id: string, column: KanbanColumn): Promise<Card> {
  return updateCard(id, { column });
}

export async function runCard(cardId: string): Promise<void> {
  await apiFetch(`/cards/${cardId}/run`, { method: "POST" });
}

/* ---------- métricas / insights (Fase C1, endpoint protegido) ---------- */
export interface MetricsInsights {
  days: number;
  total_cost_usd: number;
  cost_by_project: Record<
    string,
    { name: string; cost_usd: number; exec_count: number }
  >;
  cost_by_agent: Record<string, { cost_usd: number; exec_count: number }>;
  avg_time_per_phase: Record<string, number>;
  auto_approve_rate: number;
  reversal_rate: number;
  spend_vs_limit: { spent_usd: number; limit_usd: number; ratio: number };
}

/**
 * Consome GET /metrics/insights?days=N (motor de métricas C1).
 * Endpoint protegido por JWT — usa o fetch auth-aware (Bearer + refresh de 401).
 */
export async function getMetricsInsights(
  days = 30,
): Promise<MetricsInsights> {
  const r = await apiGet<Envelope<MetricsInsights>>(
    `/metrics/insights?days=${days}`,
  );
  return r.data;
}

/* ---------- grafo de preferências (Fase D1 / F-010 §5) ---------- */
export interface PreferenceGraphNode {
  id: string;
  label: string;
  kind: "preference";
  attribute: string;
  value: string;
  confidenceCount: number;
  archived: boolean;
  lastReinforcedAt: string | null;
}

export interface PreferenceGraphEdge {
  source: string;
  target: string;
  weight: number;
  kind: "lexical" | "co_occurrence";
}

export interface PreferenceGraphStats {
  nodes: number;
  edges: number;
  edges_per_node: number;
  linked_nodes: number;
  isolated_pct: number;
  applied_nodes: number;
  archived_nodes: number;
}

export interface PreferenceGraph {
  nodes: PreferenceGraphNode[];
  edges: PreferenceGraphEdge[];
  stats: PreferenceGraphStats;
}

/**
 * Consome GET /users/{userId}/preferences/graph (grafo de preferências D1).
 * Endpoint protegido por JWT — usa o fetch auth-aware (Bearer + refresh de 401).
 */
export async function getPreferenceGraph(
  userId: string,
): Promise<PreferenceGraph> {
  const r = await apiGet<Envelope<PreferenceGraph>>(
    `/users/${userId}/preferences/graph`,
  );
  return r.data;
}

/* ---------- projects + PRD seed ---------- */
export const DEFAULT_PROJECT_NAME = "PRD v1.1 — Pipeline Multi-Agente";

export async function ensureProject(): Promise<string> {
  const list = await apiGet<Envelope<Array<{ id: string; name: string }>>>(
    "/projects?per_page=100",
  );
  const found = (list.data || []).find((p) => p.name === DEFAULT_PROJECT_NAME);
  if (found) return found.id;
  const created = await apiSend<Envelope<{ id: string }>>("POST", "/projects", {
    name: DEFAULT_PROJECT_NAME,
    description: "Board Kanban do PRD v1.1",
  });
  return created.data.id;
}

/** Lista projetos (auth-aware) para populuar seletores de UI. */
export async function listProjects(): Promise<Array<{ id: string; name: string }>> {
  const list = await apiGet<Envelope<Array<{ id: string; name: string }>>>(
    "/projects?per_page=100",
  );
  return list.data || [];
}

/** Plano padrão do PRD v1.1 (migrado do board HTML legado). */
export const PRD_PLAN: Array<{
  code: string;
  title: string;
  agent: string;
  priority: "P0" | "P1";
  estimate: number;
  phase: string;
  column: KanbanColumn;
  deps: string[];
  description: string;
  checklist: string[];
}> = [
  { code: "CARD-001", title: "Validação manual do pipeline", agent: "Human + Agentes", priority: "P0", estimate: 8, phase: "fase0", column: "backlog", deps: [], description: "Testar o pipeline completo manualmente com 3 ideias reais antes de investir em código.", checklist: ["Ideia 1 (web app) testada", "Ideia 2 (API) testada", "Ideia 3 (landing page) testada", "Taxa de aprovação > 60% registrada", "Relatório de validação escrito"] },
  { code: "CARD-002", title: "Protocolo de comunicação entre agentes", agent: "Planner Agent + Human", priority: "P0", estimate: 4, phase: "fase0", column: "backlog", deps: ["CARD-001"], description: "Definir schemas JSON de handoff entre agentes, incluindo os schemas de integração MCP com SRA e Firecrawl.", checklist: ["Schema de cada agente definido", "Protocolo de erro documentado", "Exemplos de handoff bem/mal sucedido"] },
  { code: "CARD-003", title: "Setup da rede Docker (agentflow-net)", agent: "Human", priority: "P0", estimate: 3, phase: "fase0", column: "backlog", deps: ["CARD-001"], description: "Criar rede Docker compartilhada entre AgentFlow Studio, SRA e Firecrawl; validar conectividade entre os três containers.", checklist: ["Rede Docker criada", "SRA acessível por nome de serviço", "Firecrawl acessível por nome de serviço", "Health checks documentados"] },
  { code: "CARD-101", title: "Setup de infraestrutura", agent: "Dev Agent", priority: "P0", estimate: 6, phase: "fase1", column: "backlog", deps: ["CARD-003"], description: "Configurar docker-compose do AgentFlow Studio, SQLite, FastAPI, e conexão com a rede agentflow-net.", checklist: ["docker-compose.yml funcional", "FastAPI rodando em localhost:8000", "Health check GET /health retorna 200", "README de setup em <5min"] },
  { code: "CARD-102", title: "Modelagem do banco de dados", agent: "Dev Agent", priority: "P0", estimate: 10, phase: "fase1", column: "backlog", deps: ["CARD-101"], description: "Criar schema, migrations e models para todas as entidades, incluindo UserPreference, BudgetLimit, ResearchCache e o campo license em Snippet.", checklist: ["Tabelas principais criadas", "UserPreference, BudgetLimit, ResearchCache criadas", "Campo license em Snippet", "Migrations funcionando", "Seed data para testes"] },
  { code: "CARD-103", title: "API REST (CRUD)", agent: "Dev Agent", priority: "P0", estimate: 12, phase: "fase1", column: "backlog", deps: ["CARD-102"], description: "Implementar endpoints REST para CRUD de todas as entidades com validação e documentação OpenAPI.", checklist: ["Endpoints CRUD completos", "Validação Pydantic", "Autenticação stub", "Testes > 70% cobertura", "Swagger em /docs"] },
  { code: "CARD-104", title: "Interface Kanban (frontend, 6 colunas)", agent: "Dev Agent", priority: "P0", estimate: 18, phase: "fase1", column: "backlog", deps: ["CARD-103"], description: "Construir o board Kanban real do produto (Backlog, Researching, Planning, Reviewing, Production, Done) com drag-and-drop.", checklist: ["6 colunas visuais", "Cards arrastáveis", "Modal de detalhes", "Conexão com API REST", "Design responsivo"] },
  { code: "CARD-105", title: "Ideation Agent (Gemini)", agent: "Dev Agent", priority: "P0", estimate: 8, phase: "fase1", column: "backlog", deps: ["CARD-103"], description: "Integrar Gemini 2.5 Pro para transformar ideia bruta em JSON estruturado.", checklist: ["Endpoint /agents/ideation/run", "Timeout 30s, retry 2x", "Logs de execução salvos", "Custo por execução registrado"] },
  { code: "CARD-106", title: "Sistema de execução (queue + worker)", agent: "Dev Agent", priority: "P0", estimate: 10, phase: "fase1", column: "backlog", deps: ["CARD-105"], description: "Fila e worker assíncrono para processar jobs de agentes com retry e status tracking.", checklist: ["Worker assíncrono funcional", "Status real-time", "Retry com backoff", "Notificação de falha"] },
  { code: "CARD-107", title: "Cliente MCP + circuit breaker", agent: "Dev Agent", priority: "P0", estimate: 8, phase: "fase1", column: "backlog", deps: ["CARD-106"], description: "Cliente MCP genérico para consumir SRA e Firecrawl, com fallback REST e circuit breaker após 3 falhas seguidas.", checklist: ["Cliente MCP funcional", "Fallback REST implementado", "Circuit breaker após 3 falhas", "Timeout configurável"] },
  { code: "CARD-201", title: "Research Agent (integração SRA)", agent: "Dev Agent", priority: "P0", estimate: 10, phase: "fase2", column: "backlog", deps: ["CARD-107"], description: "Research Agent delega pesquisa de mercado/concorrentes ao Smart Research Agent via MCP.", checklist: ["Query montada a partir do Ideation Agent", "Relatório salvo como Artifact", "Cache de pesquisas recentes (7 dias)", "Circuit breaker testado"] },
  { code: "CARD-202", title: "Code Research Agent (GitHub API + Firecrawl + licença)", agent: "Dev Agent", priority: "P0", estimate: 14, phase: "fase2", column: "backlog", deps: ["CARD-201"], description: "Analisa repositórios candidatos via GitHub API, complementa com Firecrawl para conteúdo fora do GitHub, e classifica licença.", checklist: ["Leitura de README/estrutura via GitHub API", "Firecrawl usado só para fontes externas", "Classificação de licença (permissiva/copyleft/desconhecida)", "Aviso visual para copyleft", "Nunca copia código automaticamente"] },
  { code: "CARD-203", title: "Planner Agent", agent: "Dev Agent", priority: "P0", estimate: 10, phase: "fase2", column: "backlog", deps: ["CARD-202"], description: "Gera plano de execução com fases, milestones, stack e riscos, considerando também Research e Code Research.", checklist: ["Input inclui Research + Code Research", "Stack recomendada considera padrões encontrados", "Risk register com mitigação"] },
  { code: "CARD-204", title: "Reviewer Agent (leve)", agent: "Dev Agent", priority: "P1", estimate: 6, phase: "fase2", column: "backlog", deps: ["CARD-203"], description: "Audita consistência entre ideia, pesquisa e plano antes de partir para código, sem bloquear o pipeline.", checklist: ["Detecta contradições entre ideia e plano", "Alertas aparecem no modal de aprovação", "Não bloqueia avanço, só sinaliza"] },
  { code: "CARD-205", title: "Dev Agent + sandbox de validação", agent: "Dev Agent", priority: "P0", estimate: 22, phase: "fase2", column: "backlog", deps: ["CARD-204"], description: "Gera código e valida em container efêmero antes de entregar, com até 2 tentativas de autocorreção.", checklist: ["Código gerado por camada", "Execução em container --rm sem rede", "Autocorreção até 2 tentativas", "Aviso se falhar após tentativas"] },
  { code: "CARD-206", title: "Human-in-the-Loop Gate + auto-approve", agent: "Dev Agent", priority: "P0", estimate: 18, phase: "fase2", column: "backlog", deps: ["CARD-205"], description: "Sistema de aprovação manual com opção de auto-approve quando confidence score é alto e não há alertas do Reviewer.", checklist: ["Modal de aprovação com tabs", "Auto-approve com confidence >= 0.85", "Janela de reversão de 30min", "Opção de desativar auto-approve"] },
  { code: "CARD-207", title: "Snippet Library + licença", agent: "Dev Agent", priority: "P1", estimate: 10, phase: "fase2", column: "backlog", deps: ["CARD-202"], description: "CRUD de snippets reutilizáveis com campo de licença obrigatório e aviso visual para copyleft.", checklist: ["CRUD completo", "Campo license obrigatório", "Aviso visual para GPL/AGPL", "Busca por texto e tags"] },
  { code: "CARD-208", title: "Perfil de preferências do usuário", agent: "Dev Agent", priority: "P1", estimate: 12, phase: "fase2", column: "backlog", deps: ["CARD-206"], description: "Aprende preferências de stack/estilo a partir de edições e rejeições, aplicando só após 2+ reforços.", checklist: ["Tabela user_preferences populada automaticamente", "Tela em Configurações para editar/remover", "Confiança mínima de 2 reforços antes de aplicar"] },
  { code: "CARD-209", title: "Cap de orçamento", agent: "Dev Agent", priority: "P1", estimate: 8, phase: "fase2", column: "backlog", deps: ["CARD-206"], description: "Limite de gasto configurável por usuário e por projeto, com aviso em 80% e bloqueio em 100%.", checklist: ["Limite mensal e por projeto configuráveis", "Aviso em 80%", "Bloqueio em 100%", "Reset mensal automático"] },
  { code: "CARD-301", title: "Onboarding interativo", agent: "Dev Agent", priority: "P1", estimate: 10, phase: "fase3", column: "backlog", deps: ["CARD-104"], description: "Tour guiado de primeiro uso com template de projeto pré-configurado.", checklist: ["5 passos de tour", "Template pré-configurado", "Badge de conclusão", "Opção de pular"] },
  { code: "CARD-302", title: "Dashboard de métricas (simplificado)", agent: "Dev Agent", priority: "P1", estimate: 4, phase: "fase3", column: "backlog", deps: ["CARD-209"], description: "Versão simplificada: cards de métricas essenciais e tabela de execuções, sem gráficos no MVP.", checklist: ["Cards de projetos/custo/tempo", "Tabela de execuções com filtros"] },
  { code: "CARD-303", title: "UX polish", agent: "Dev Agent", priority: "P1", estimate: 10, phase: "fase3", column: "backlog", deps: ["CARD-301", "CARD-302"], description: "Animações, estados de loading, empty states e dark mode.", checklist: ["Animações de transição", "Skeleton loaders", "Empty states", "Dark mode"] },
  { code: "CARD-304", title: "Deploy e monitoramento", agent: "Dev Agent", priority: "P0", estimate: 6, phase: "fase3", column: "backlog", deps: ["CARD-303"], description: "Deploy em produção com domínio, SSL, backup e monitoramento.", checklist: ["Deploy automático via CI", "Domínio + SSL", "Backup automático", "Monitoramento ativo"] },
  { code: "CARD-401", title: "Go-to-market", agent: "Human", priority: "P1", estimate: 16, phase: "fase35", column: "backlog", deps: ["CARD-304"], description: "Landing page, SEO, comunidade e lançamento no Product Hunt.", checklist: ["Landing page publicizada", "3 posts de blog (SEO)", "Comunidade criada", "Product Hunt preparado"] },
  { code: "CARD-402", title: "Beta launch", agent: "Human + Beta testers", priority: "P0", estimate: 16, phase: "fase35", column: "backlog", deps: ["CARD-401"], description: "Convidar beta testers, coletar feedback estruturado e decidir sobre lançamento público.", checklist: ["10-20 beta testers convidados", "Formulário de feedback estruturado", "Métricas de NPS e uso coletadas", "Decisão de lançar ou iterar"] },
];

export async function seedPlan(projectId: string): Promise<void> {
  for (const m of PRD_PLAN) {
    await createCard({
      project_id: projectId,
      title: m.title,
      column: m.column,
      meta: {
        code: m.code,
        agent: m.agent,
        priority: m.priority,
        estimate: m.estimate,
        phase: m.phase,
        description: m.description,
        deps: m.deps,
        checklist: m.checklist.map((text) => ({ text, done: false })),
      },
    });
  }
}
