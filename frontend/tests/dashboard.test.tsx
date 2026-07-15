import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Dashboard } from "../src/components/dashboard/Dashboard";

const insightsSample = {
  days: 30,
  total_cost_usd: 9.0,
  cost_by_project: {
    p1: { name: "Projeto A", cost_usd: 4.0, exec_count: 3 },
    p2: { name: "Projeto B", cost_usd: 5.0, exec_count: 1 },
  },
  cost_by_agent: {
    dev: { cost_usd: 3.0, exec_count: 2 },
    reviewer: { cost_usd: 5.0, exec_count: 1 },
  },
  avg_time_per_phase: { dev: 2000, reviewer: 2000 },
  auto_approve_rate: 0.3333,
  reversal_rate: 0.3333,
  spend_vs_limit: { spent_usd: 8, limit_usd: 100, ratio: 0.08 },
};

const sample = {
  projects_created: 3,
  cards_done: 1,
  total_cost_usd: 1.23,
  spend_vs_limit: { spent_usd: 5, limit_usd: 10, ratio: 0.5 },
  recent_executions: [
    {
      id: "e1",
      card_id: "c1",
      agent_name: "ideation",
      status: "success",
      duration_ms: 1200,
      cost_usd: 0.01,
    },
  ],
  cost_by_day: [
    { date: "2026-07-13", cost_usd: 0.01 },
    { date: "2026-07-12", cost_usd: 0.02 },
  ],
  cost_by_agent: [
    { agent_name: "ideation", cost_usd: 0.01, exec_count: 1 },
    { agent_name: "dev", cost_usd: 0.5, exec_count: 2 },
  ],
  executions_by_status: { success: 2, failed: 1, running: 0, pending: 0 },
};

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/metrics/insights")) {
        return {
          ok: true,
          json: async () => ({ success: true, data: insightsSample }),
        };
      }
      if (url.includes("/projects")) {
        return {
          ok: true,
          json: async () => ({
            success: true,
            data: [
              { id: "p1", name: "Projeto A" },
              { id: "p2", name: "Projeto B" },
            ],
          }),
        };
      }
      return { ok: true, json: async () => ({ success: true, data: sample }) };
    }),
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza métricas essenciais (F-013)", async () => {
    stubFetch();
    render(<Dashboard />);
    expect(await screen.findByText("3")).toBeTruthy(); // projetos
    expect(await screen.findByText("$1.23")).toBeTruthy(); // custo total
  });

  it("renderiza tabela de execuções recentes", async () => {
    stubFetch();
    render(<Dashboard />);
    expect(await screen.findByText("ideation")).toBeTruthy();
    expect(await screen.findByText("success")).toBeTruthy();
  });

  it("renderiza séries v1.2 (custo por dia, por agente, status)", async () => {
    stubFetch();
    render(<Dashboard />);
    // gráfico de custo por dia
    expect(await screen.findByText("Custo por dia (30 dias)")).toBeTruthy();
    // gráfico de custo por agente
    expect(await screen.findByText("Custo por agente")).toBeTruthy();
    // contadores por status
    expect(await screen.findByText("success: 2")).toBeTruthy();
    expect(await screen.findByText("failed: 1")).toBeTruthy();
    // seletor de projeto populado
    await waitFor(() => expect(screen.getByText("Projeto A")).toBeTruthy());
  });

  it("renderiza painel de insights (C1: custo por projeto, taxas, tempo por fase)", async () => {
    stubFetch();
    render(<Dashboard />);
    // título do painel + taxas derivadas do endpoint /metrics/insights
    expect(await screen.findByText("Insights")).toBeTruthy();
    expect(await screen.findByText("Taxa de auto-approve")).toBeTruthy();
    expect(await screen.findByText("Taxa de reversão")).toBeTruthy();
    // 0.3333 -> 33%
    const rates = await screen.findAllByText("33%");
    expect(rates.length).toBeGreaterThanOrEqual(2);
    // gráfico de custo por projeto + tempo médio por fase
    expect(await screen.findByText("Custo por projeto")).toBeTruthy();
    expect(await screen.findByText("Tempo médio por fase")).toBeTruthy();
  });

  it("estado de erro", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<Dashboard />);
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
