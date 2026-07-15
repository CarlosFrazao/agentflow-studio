import type { Card, CardMeta } from "../../types/card";

interface Props {
  card: Card;
  onOpen: (id: string) => void;
  onDragStart: (id: string) => void;
  onDragEnd: () => void;
}

const PRIORITY_STYLE: Record<string, string> = {
  P0: "bg-[var(--p0-bg)] text-[var(--p0)]",
  P1: "bg-[var(--p1-bg)] text-[var(--p1)]",
  P2: "bg-[var(--surface)] text-[var(--text-2)]",
};

const PHASE_CLASS: Record<string, string> = {
  fase0: "phase0",
  fase1: "phase1",
  fase2: "phase2",
  fase3: "phase3",
  fase35: "phase35",
};

const PHASE_HEX: Record<string, string> = {
  fase0: "var(--phase0)",
  fase1: "var(--phase1)",
  fase2: "var(--phase2)",
  fase3: "var(--phase3)",
  fase35: "var(--phase35)",
};

const PHASE_LABEL: Record<string, string> = {
  fase0: "Fase 0",
  fase1: "Fase 1",
  fase2: "Fase 2",
  fase3: "Fase 3",
  fase35: "Fase 3.5/Beta",
};

const AGENT_PALETTE = [
  "#2dd4bf", "#38bdf8", "#a78bfa", "#f5a524", "#f472b6",
  "#34d399", "#fb7185", "#60a5fa", "#fbbf24", "#c084fc",
];

function agentColor(name: string): string {
  const key = (name || "").toLowerCase();
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return AGENT_PALETTE[h % AGENT_PALETTE.length];
}

function agentInitials(name: string): string {
  const parts = (name || "").split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function KanbanCard({ card, onOpen, onDragStart, onDragEnd }: Props) {
  const meta = (card.meta || {}) as CardMeta;
  const checklist = meta.checklist ?? [];
  const done = checklist.filter((c) => c.done).length;
  const pct = checklist.length ? Math.round((done / checklist.length) * 100) : 0;
  const phase = meta.phase ?? "";

  return (
    <article
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", card.id);
        e.dataTransfer.effectAllowed = "move";
        onDragStart(card.id);
      }}
      onDragEnd={onDragEnd}
      onClick={() => onOpen(card.id)}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen(card.id);
      }}
      className="af-fade cursor-grab rounded-[var(--radius-sm)] border border-[var(--border)] border-l-[3px] border-l-[var(--phase1)] bg-[var(--surface-2)] p-[11px_12px] transition-[background,border-color,transform] hover:-translate-y-px hover:bg-[var(--surface-3)] hover:shadow-[var(--shadow-sm)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
      aria-label={`Card ${card.title}`}
    >
      <div className="mb-1.5 flex items-start justify-between gap-2">
        <span className="font-mono text-[10.5px] text-[var(--muted)]">
          {meta.code ?? card.id.slice(0, 8)}
        </span>
        {meta.priority && (
          <span
            className={`rounded-[20px] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.03em] ${
              PRIORITY_STYLE[meta.priority] ?? PRIORITY_STYLE.P2
            }`}
          >
            {meta.priority}
          </span>
        )}
      </div>

      <h3 className="mb-1.5 text-[13px] font-semibold leading-snug text-[var(--text)]">
        {card.title}
      </h3>

      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        {phase && (
          <span
            className={`rounded-[20px] px-2 py-0.5 text-[10.5px] ${
              PHASE_CLASS[phase] ?? ""
            }`}
            style={{
              color: PHASE_HEX[phase] ?? "var(--text-2)",
              background: `color-mix(in srgb, ${PHASE_HEX[phase] ?? "var(--text-2)"} 14%, transparent)`,
            }}
          >
            {PHASE_LABEL[phase] ?? phase}
          </span>
        )}
        {card.auto_approved && (
          <span
            className="inline-flex items-center gap-1 rounded-[20px] border border-[var(--accent)] bg-[var(--accent-soft)] px-2 py-0.5 text-[10.5px] font-semibold text-[var(--accent-text)]"
            title="Aprovado automaticamente pelo sistema (ADR-007)"
          >
            🤖 Auto-aprovado
          </span>
        )}
        {meta.agent && (
          <span className="inline-flex items-center gap-1.5 rounded-[20px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-[10.5px] text-[var(--text-2)]">
            <span
              className="grid h-[17px] w-[17px] place-items-center rounded-full text-[8.5px] font-extrabold text-[#06121a]"
              style={{ background: agentColor(meta.agent) }}
            >
              {agentInitials(meta.agent)}
            </span>
            {meta.agent}
          </span>
        )}
        {meta.estimate != null && (
          <span className="rounded-[20px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-[10.5px] text-[var(--text-2)]">
            {meta.estimate}h
          </span>
        )}
      </div>

      {checklist.length > 0 && (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
            <div
              className="h-full rounded-full transition-[width] [background:linear-gradient(90deg,var(--accent),var(--accent-2))]"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="font-mono text-[10px] text-[var(--muted)]">
            {done}/{checklist.length}
          </span>
        </div>
      )}
    </article>
  );
}
