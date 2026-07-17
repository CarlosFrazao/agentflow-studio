import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor, act } from "@testing-library/react";
import { useBoardStore } from "../../store/useBoardStore";
import type { Card } from "../../types/card";

// --- Mocks ---
const closeWs = vi.fn();
const connectShareWs = vi.fn(() => ({ close: closeWs }));
vi.mock("../../api/shareWs", () => ({
  connectShareWs: () => connectShareWs(),
}));

const listCards = vi.fn(() => Promise.resolve([] as Card[]));
vi.mock("../../api/client", () => ({
  ensureProject: () => Promise.resolve("proj-1"),
  listCards: () => listCards(),
  seedPlan: () => Promise.resolve(),
  moveCard: () => Promise.resolve({} as Card),
}));

vi.mock("../../auth", () => ({
  getToken: () => "tok",
  getRefreshToken: () => null,
  refreshAccessToken: () => Promise.resolve(false),
  clearToken: () => undefined,
  isLoggedIn: () => true,
}));

import { KanbanBoard } from "./KanbanBoard";

function makeCard(id: string, title: string, column: Card["column"] = "backlog"): Card {
  return {
    id,
    project_id: "proj-1",
    column,
    title,
    order_index: 0,
    confidence_score: 0,
    approval_by: "none",
    auto_approved: false,
    revert_deadline: null,
    meta: {},
    created_at: "",
    updated_at: "",
  };
}

beforeEach(() => {
  useBoardStore.setState({ cards: [], filters: { phase: "", priority: "", search: "" } });
  connectShareWs.mockClear();
  closeWs.mockClear();
  listCards.mockReset();
  listCards.mockResolvedValue([] as Card[]);
});

afterEach(() => {
  cleanup();
});

describe("useBoardStore (FEAT-003)", () => {
  it("replaceCard atualiza um card existente in-place (sem duplicar)", () => {
    useBoardStore.getState().setCards([makeCard("c1", "Ideia A", "backlog")]);

    useBoardStore.getState().replaceCard(makeCard("c1", "Ideia A (revisada)", "researching"));
    const afterUpdate = useBoardStore.getState().cards;
    expect(afterUpdate).toHaveLength(1);
    expect(afterUpdate[0].title).toBe("Ideia A (revisada)");
    expect(afterUpdate[0].column).toBe("researching");
  });

  it("setCards adiciona um novo card ao board", () => {
    useBoardStore.getState().setCards([makeCard("c1", "Ideia A", "backlog")]);
    useBoardStore.getState().setCards([
      ...useBoardStore.getState().cards,
      makeCard("c2", "Ideia B", "backlog"),
    ]);
    const afterAdd = useBoardStore.getState().cards;
    expect(afterAdd).toHaveLength(2);
    expect(afterAdd.find((c) => c.id === "c2")).toBeTruthy();
  });
});

describe("KanbanBoard (FEAT-003)", () => {
  it("subscreve o store: atualização do card.updated aparece sem nova chamada à API", async () => {
    const card = makeCard("ws-1", "Card original", "backlog");
    listCards.mockResolvedValue([card]);

    render(<KanbanBoard />);

    // Carga inicial da API mostra o card.
    await waitFor(() => {
      expect(screen.getByText("Card original")).toBeTruthy();
    });
    const callsAfterLoad = listCards.mock.calls.length;

    // Simula o evento card.updated do WS aplicado no store (shareWs já faz isso).
    act(() => {
      useBoardStore.getState().replaceCard(makeCard("ws-1", "Card atualizado via WS", "researching"));
    });

    await waitFor(() => {
      expect(screen.getByText("Card atualizado via WS")).toBeTruthy();
    });
    // O board reagiu ao store; nenhuma chamada extra à API foi feita.
    expect(listCards.mock.calls.length).toBe(callsAfterLoad);
    expect(connectShareWs).toHaveBeenCalled();
  });

  it("faz cleanup do listener WS ao desmontar (sem vazamento)", async () => {
    const { unmount } = render(<KanbanBoard />);

    await waitFor(() => {
      expect(connectShareWs).toHaveBeenCalled();
    });
    expect(closeWs).not.toHaveBeenCalled();

    unmount();
    expect(closeWs).toHaveBeenCalledTimes(1);
  });
});
