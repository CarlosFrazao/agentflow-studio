import { create } from "zustand";
import type { Card, KanbanColumn } from "../types/card";

export type BoardView = "kanban" | "dashboard";

export interface BoardFilters {
  phase: string; // "" = todas
  priority: "" | "P0" | "P1" | "P2";
  search: string;
}

interface BoardState {
  cards: Card[];
  filters: BoardFilters;
  view: BoardView;

  setCards: (cards: Card[]) => void;
  setView: (view: BoardView) => void;
  setFilter: <K extends keyof BoardFilters>(key: K, value: BoardFilters[K]) => void;
  resetFilters: () => void;

  /** Atualização otimista de coluna (rollback é feito por quem chama em caso de erro). */
  moveOptimistic: (cardId: string, column: KanbanColumn) => void;
  /** Reaplica o estado do servidor para um card após erro/refresh. */
  replaceCard: (card: Card) => void;
}

const EMPTY_FILTERS: BoardFilters = { phase: "", priority: "", search: "" };

export const useBoardStore = create<BoardState>((set) => ({
  cards: [],
  filters: EMPTY_FILTERS,
  view: "kanban",

  setCards: (cards) => set({ cards }),
  setView: (view) => set({ view }),
  setFilter: (key, value) =>
    set((s) => ({ filters: { ...s.filters, [key]: value } })),
  resetFilters: () => set({ filters: EMPTY_FILTERS }),

  moveOptimistic: (cardId, column) =>
    set((s) => ({
      cards: s.cards.map((c) => (c.id === cardId ? { ...c, column } : c)),
    })),
  replaceCard: (card) =>
    set((s) => ({
      cards: s.cards.map((c) => (c.id === card.id ? card : c)),
    })),
}));

/** Seletor puro para filtrar cards (usado no board e no export). */
export function selectFilteredCards(
  cards: Card[],
  filters: BoardFilters,
): Card[] {
  const q = filters.search.trim().toLowerCase();
  return cards.filter((c) => {
    if (filters.phase && (c.meta?.phase ?? "") !== filters.phase) return false;
    if (filters.priority && (c.meta?.priority ?? "") !== filters.priority) return false;
    if (q) {
      const hay = `${c.title} ${c.meta?.code ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}
