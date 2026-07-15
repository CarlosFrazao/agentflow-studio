import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { KanbanBoard } from "../src/components/kanban/KanbanBoard";
import { COLUMN_LABELS, COLUMN_ORDER } from "../src/types/card";

const sampleCards = [
  {
    id: "1",
    project_id: "p1",
    column: "backlog" as const,
    title: "Ideia A",
    order_index: 0,
    confidence_score: 0.9,
    approval_by: "auto" as const,
    auto_approved: true,
    revert_deadline: null,
    created_at: "2026-07-11T00:00:00Z",
    updated_at: "2026-07-11T00:00:00Z",
  },
];

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza as 6 colunas do pipeline (PRD F-001)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: [], meta: { request_id: "r", timestamp: "" } }),
      }),
    );
    render(<KanbanBoard />);
    for (const col of COLUMN_ORDER) {
      expect(await screen.findByLabelText(`Coluna ${COLUMN_LABELS[col]}`)).toBeTruthy();
    }
  });

  it("mostra badge 'Auto-aprovado' para cards aprovados pelo sistema (ADR-007)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: sampleCards, meta: { request_id: "r", timestamp: "" } }),
      }),
    );
    render(<KanbanBoard />);
    expect(await screen.findByText(/Auto-aprovado/)).toBeTruthy();
  });

  it("estado de loading aparece antes dos dados", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    render(<KanbanBoard />);
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("estado de erro com botao de retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<KanbanBoard />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(await screen.findByText(/Tentar novamente/)).toBeTruthy();
  });

  it("coluna vazia mostra estado empty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: [], meta: { request_id: "r", timestamp: "" } }),
      }),
    );
    render(<KanbanBoard />);
    expect(await screen.findAllByText(/Nenhum card/)).toHaveLength(COLUMN_ORDER.length);
  });
});
