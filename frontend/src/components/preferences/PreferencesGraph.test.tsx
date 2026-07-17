import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { PreferencesGraph } from "./PreferencesGraph";

const sampleGraph = {
  nodes: [
    { id: "n1", label: "stack: react", kind: "preference", attribute: "stack", value: "react", confidenceCount: 3, archived: false, lastReinforcedAt: null },
    { id: "n2", label: "stack: vue", kind: "preference", attribute: "stack", value: "vue", confidenceCount: 2, archived: false, lastReinforcedAt: null },
  ],
  edges: [
    { source: "n1", target: "n2", weight: 1, kind: "co_occurrence" },
  ],
  stats: { nodes: 2, edges: 1, edges_per_node: 0.5, linked_nodes: 2, isolated_pct: 0, applied_nodes: 2, archived_nodes: 0 },
};

const getPreferenceGraph = vi.fn();
vi.mock("../../api/client", () => ({
  getPreferenceGraph: (userId: string) => getPreferenceGraph(userId),
}));

vi.mock("../../auth", () => ({
  getUserId: () => "user-123",
}));

beforeEach(() => {
  localStorage.clear();
  getPreferenceGraph.mockReset();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PreferencesGraph (F-010 §5)", () => {
  it("desenha os nós do grafo a partir do endpoint", async () => {
    getPreferenceGraph.mockResolvedValue(sampleGraph);
    render(<PreferencesGraph />);
    await waitFor(() => {
      expect(screen.getByText("react")).toBeTruthy();
    });
    expect(screen.getByText("vue")).toBeTruthy();
    // Chama o endpoint com o userId do auth.
    expect(getPreferenceGraph).toHaveBeenCalledWith("user-123");
  });

  it("mostra estado de erro acessível quando a chamada falha", async () => {
    getPreferenceGraph.mockRejectedValue(new Error("HTTP 500"));
    render(<PreferencesGraph />);
    const alert = await waitFor(() => screen.findByRole("alert"));
    expect(alert.textContent).toMatch(/não.*carregar|falha/i);
  });
});
