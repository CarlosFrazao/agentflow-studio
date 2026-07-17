import { useEffect, useMemo, useRef, useState } from "react";
import { COLUMN_LABELS, COLUMN_ORDER, type KanbanColumn } from "../../types/card";
import {
  ensureProject,
  listCards,
  moveCard,
  seedPlan,
} from "../../api/client";
import { connectShareWs, type ShareWsHandle } from "../../api/shareWs";
import { KanbanCard } from "./KanbanCard";
import { CardModal } from "./CardModal";
import { toast } from "../../store/useToastStore";
import { useBoardStore, selectFilteredCards } from "../../store/useBoardStore";

const PHASES = ["fase0", "fase1", "fase2", "fase3", "fase35"];
const PHASE_LABEL: Record<string, string> = {
  fase0: "Fase 0",
  fase1: "Fase 1",
  fase2: "Fase 2",
  fase3: "Fase 3",
  fase35: "Fase 3.5/Beta",
};

const COLUMN_COLOR: Record<KanbanColumn, string> = {
  backlog: "var(--muted)",
  researching: "var(--accent-2)",
  planning: "var(--accent)",
  reviewing: "var(--warn)",
  production: "var(--ok)",
  done: "var(--ok)",
};

export function KanbanBoard() {
  // Estado derivado do servidor vive no useBoardStore (fonte única de verdade).
  // O WS (card.updated) atualiza o store em tempo real; o board apenas lê.
  const cards = useBoardStore((s) => s.cards);
  const setStoreCards = useBoardStore((s) => s.setCards);
  const filters = useBoardStore((s) => s.filters);
  const setFilter = useBoardStore((s) => s.setFilter);
  const resetFilters = useBoardStore((s) => s.resetFilters);
  const moveOptimistic = useBoardStore((s) => s.moveOptimistic);
  const replaceCard = useBoardStore((s) => s.replaceCard);

  const [loadError, setLoadError] = useState<string>("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<
    "idle" | "connecting" | "open" | "closed"
  >("idle");
  const [modalCardId, setModalCardId] = useState<string | null | undefined>(undefined);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dropCol, setDropCol] = useState<KanbanColumn | null>(null);

  const projectIdRef = useRef<string | null>(null);

  // Carga inicial SÓ no mount. O WS (card.updated) mantém o store atualizado
  // sem refresh, evitando loop de re-render entre load() e store (ADR A3).
  async function load() {
    try {
      const pid = await ensureProject();
      projectIdRef.current = pid;
      const existing = await listCards({ projectId: pid });
      if (existing.length === 0) {
        await seedPlan(pid);
      }
      const data = await listCards({ projectId: pid });
      setStoreCards(data);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setInitialLoading(false);
    }
  }

  useEffect(() => {
    let ws: ShareWsHandle | null = null;
    let cancelled = false;
    (async () => {
      await load();
      const pid = projectIdRef.current;
      if (pid && !cancelled) {
        ws = connectShareWs(pid, { onStatus: (s) => setConnectionStatus(s) });
      }
    })();
    return () => {
      cancelled = true;
      ws?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(
    () => selectFilteredCards(cards, filters),
    [cards, filters],
  );

  async function handleDrop(col: KanbanColumn) {
    setDropCol(null);
    const id = dragId;
    setDragId(null);
    if (!id) return;
    const card = cards.find((c) => c.id === id);
    if (!card || card.column === col) return;
    // Atualização otimista via store; rollback reaplica o estado do servidor se falhar.
    moveOptimistic(id, col);
    try {
      await moveCard(id, col);
      toast.info("Card movido", `${card.meta?.code ?? id} → ${COLUMN_LABELS[col]}`);
    } catch (e) {
      replaceCard(card);
      toast.error("Erro ao mover", e instanceof Error ? e.message : undefined);
    }
  }

  const btnPrimary =
    "inline-flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-[13px] font-semibold text-[#06121a] transition-[filter] [background:linear-gradient(135deg,var(--accent),var(--accent-2))] hover:brightness-110";

  if (initialLoading) {
    return (
      <div className="flex h-40 items-center justify-center text-[var(--muted)]" role="status" aria-live="polite">
        Carregando board…
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="rounded-[14px] border border-[var(--danger)] bg-[var(--danger-bg)] p-4 text-[var(--danger)]" role="alert">
        <p className="font-medium">Falha ao carregar o board.</p>
        <p className="text-sm">{loadError}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-2 rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-3)]"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div className="af-fade">
      {/* Toolbar de filtros */}
      <div className="mb-[18px] flex flex-wrap items-center gap-[10px]">
        <select
          value={filters.phase}
          onChange={(e) => setFilter("phase", e.target.value)}
          aria-label="Filtrar por fase"
          className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[13px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
        >
          <option value="">Todas as fases</option>
          {PHASES.map((p) => (
            <option key={p} value={p}>
              {PHASE_LABEL[p]}
            </option>
          ))}
        </select>
        <select
          value={filters.priority}
          onChange={(e) => setFilter("priority", e.target.value as "" | "P0" | "P1" | "P2")}
          aria-label="Filtrar por prioridade"
          className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[13px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
        >
          <option value="">Todas prioridades</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
        </select>
        <input
          value={filters.search}
          onChange={(e) => setFilter("search", e.target.value)}
          placeholder="Buscar por título ou código..."
          aria-label="Buscar cards"
          className="min-w-[200px] flex-1 rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[13px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
        />
        <button
          type="button"
          onClick={() => resetFilters()}
          className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[13px] text-[var(--text-2)] transition-colors hover:bg-[var(--surface-3)]"
        >
          Limpar filtros
        </button>
        <span
          title={connectionStatus === "open" ? "Tempo real conectado" : "Atualização em tempo real indisponível"}
          className={`inline-flex items-center gap-1.5 rounded-[20px] px-2.5 py-1 text-[11px] font-medium ${
            connectionStatus === "open"
              ? "bg-[var(--accent-soft)] text-[var(--accent-text)]"
              : "bg-[var(--surface-3)] text-[var(--text-2)]"
          }`}
          role="status"
          aria-live="polite"
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              connectionStatus === "open" ? "bg-[var(--accent)]" : "bg-[var(--muted)]"
            }`}
          />
          {connectionStatus === "open" ? "Ao vivo" : "Offline"}
        </span>
        <button onClick={() => setModalCardId(null)} className={btnPrimary}>
          + Novo card
        </button>
      </div>

      {/* Board */}
      <div className="af-scroll-x flex min-w-0 gap-[16px] items-start overflow-x-auto pb-[12px]">
        {COLUMN_ORDER.map((col) => {
          const colCards = filtered.filter((c) => c.column === col);
          const isDrop = dropCol === col;
          return (
            <section
              key={col}
              onDragOver={(e) => {
                e.preventDefault();
                if (dropCol !== col) setDropCol(col);
              }}
              onDragLeave={(e) => {
                if (e.currentTarget === e.target) setDropCol(null);
              }}
              onDrop={() => void handleDrop(col)}
              className={`flex w-[300px] min-w-[300px] flex-col rounded-[var(--radius)] border bg-[var(--surface)] ${
                isDrop ? "border-[var(--accent)] shadow-[0_0_0_2px_var(--accent-soft)]" : "border-[var(--border)]"
              }`}
              aria-label={`Coluna ${COLUMN_LABELS[col]}`}
            >
              <header className="sticky top-0 flex items-center justify-between rounded-t-[var(--radius)] border-b border-[var(--border)] bg-[var(--surface)] px-[14px] py-[13px]">
                <span className="flex items-center gap-2 text-[13px] font-semibold">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: COLUMN_COLOR[col] }}
                  />
                  {COLUMN_LABELS[col]}
                </span>
                <span className="rounded-[20px] bg-[var(--surface-2)] px-2 py-0.5 font-mono text-[11px] text-[var(--muted)]">
                  {colCards.length}
                </span>
              </header>

              <div className="flex flex-1 flex-col gap-[9px] overflow-y-auto p-[11px]">
                {colCards.length === 0 ? (
                  <p className="rounded-[10px] border border-dashed border-[var(--border)] p-5 text-center text-[12px] text-[var(--muted)]">
                    Nenhum card
                  </p>
                ) : (
                  colCards.map((card) => (
                    <KanbanCard
                      key={card.id}
                      card={card}
                      onOpen={setModalCardId}
                      onDragStart={setDragId}
                      onDragEnd={() => {
                        setDragId(null);
                        setDropCol(null);
                      }}
                    />
                  ))
                )}
              </div>
            </section>
          );
        })}
      </div>

      <p className="mt-[18px] text-center text-[11.5px] text-[var(--muted)]">
        Dados sincronizados com o backend (AgentFlow API).
      </p>

      {modalCardId !== undefined && (
        <CardModal
          cardId={modalCardId}
          onClose={() => setModalCardId(undefined)}
          onChanged={() => void load()}
        />
      )}
    </div>
  );
}
