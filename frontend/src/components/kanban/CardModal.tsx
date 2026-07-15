import { useEffect, useState } from "react";
import type { CardMeta, KanbanColumn } from "../../types/card";
import { COLUMN_LABELS, COLUMN_ORDER } from "../../types/card";
import {
  createCard,
  deleteCard,
  ensureProject,
  moveCard,
  runCard,
  updateCard,
} from "../../api/client";
import { toast } from "../../store/useToastStore";

interface Props {
  /** null = criar novo card; id = editar card existente. */
  cardId: string | null;
  onClose: () => void;
  onChanged: () => void;
}

const PRIORITY_OPTIONS: Array<"P0" | "P1" | "P2"> = ["P0", "P1", "P2"];
const PHASES = ["fase0", "fase1", "fase2", "fase3", "fase35"];

export function CardModal({ cardId, onClose, onChanged }: Props) {
  const isNew = cardId === null;
  const [title, setTitle] = useState("");
  const [meta, setMeta] = useState<CardMeta>({
    code: `CARD-${Math.floor(1000 + Math.random() * 9000)}`,
    agent: "Dev Agent",
    priority: "P1",
    estimate: 4,
    phase: "fase2",
    column: "backlog",
    description: "",
    deps: [],
    checklist: [],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const checklist = meta.checklist ?? [];

  // Fecha o modal com a tecla Escape (não enquanto uma ação está em andamento).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  function patchMeta(p: Partial<CardMeta>) {
    setMeta((m) => ({ ...m, ...p }));
  }

  async function save() {
    if (!title.trim()) {
      setError("Dê um título ao card.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (isNew) {
        const pid = await ensureProject();
        await createCard({
          project_id: pid,
          title: title.trim(),
          column: (meta.column as KanbanColumn) ?? "backlog",
          meta,
        });
        toast.success("Card criado", `${meta.code} adicionado ao board.`);
      } else {
        await updateCard(cardId!, { title: title.trim(), meta });
        toast.success("Card atualizado", `${meta.code} salvo com sucesso.`);
      }
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setBusy(false);
    }
  }

  async function move(col: KanbanColumn) {
    if (!cardId) return;
    setBusy(true);
    setError("");
    try {
      await moveCard(cardId, col);
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao mover");
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    if (!cardId) return;
    setBusy(true);
    setError("");
    try {
      await runCard(cardId);
      toast.success("Agente executado", "O card foi enviado para o pipeline.");
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao executar");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!cardId) return;
    if (!confirm(`Excluir o card "${title || meta.code}"?`)) return;
    setBusy(true);
    try {
      await deleteCard(cardId);
      toast.info("Card excluído", `${meta.code} removido do board.`);
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao excluir");
    } finally {
      setBusy(false);
    }
  }

  function toggleCheck(i: number) {
    const next = checklist.map((c, idx) =>
      idx === i ? { ...c, done: !c.done } : c,
    );
    patchMeta({ checklist: next });
  }

  const field =
    "w-full rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[13px] text-[var(--text)] outline-none transition-colors focus:border-[var(--accent)]";
  const labelCls = "block text-[11px] font-semibold uppercase tracking-[0.05em] text-[var(--muted)] mb-1.5";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[rgba(6,10,15,0.62)] p-[48px_16px] backdrop-blur-[3px]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={isNew ? "Novo card" : `Detalhes do card ${title || meta.code}`}
    >
      <div
        className="af-fade w-full max-w-[580px] rounded-[16px] border border-[var(--border-strong)] bg-[var(--surface)] p-[24px_26px_20px] shadow-[var(--shadow)]"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-[17px] font-semibold">
          {isNew ? "＋ Novo card" : meta.code}
        </h2>

        <div className="mb-3 flex flex-col gap-1">
          <label className={labelCls}>Título</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título do card"
            className={field}
            aria-label="Título do card"
          />
        </div>

        <div className="grid grid-cols-2 gap-[11px]">
          <div className="flex flex-col gap-1">
            <label className={labelCls}>Agente</label>
            <input
              value={meta.agent ?? ""}
              onChange={(e) => patchMeta({ agent: e.target.value })}
              className={field}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className={labelCls}>Estimativa (h)</label>
            <input
              type="number"
              min={0}
              value={meta.estimate ?? 0}
              onChange={(e) => patchMeta({ estimate: Number(e.target.value) || 0 })}
              className={field}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className={labelCls}>Prioridade</label>
            <select
              value={meta.priority ?? "P1"}
              onChange={(e) =>
                patchMeta({ priority: e.target.value as "P0" | "P1" | "P2" })
              }
              className={field}
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className={labelCls}>Fase</label>
            <select
              value={meta.phase ?? ""}
              onChange={(e) => patchMeta({ phase: e.target.value })}
              className={field}
            >
              {PHASES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-3 flex flex-col gap-1">
          <label className={labelCls}>Descrição</label>
          <textarea
            value={meta.description ?? ""}
            onChange={(e) => patchMeta({ description: e.target.value })}
            className={`${field} min-h-[64px] resize-y`}
          />
        </div>

        <div className="mt-3">
          <label className={labelCls}>
            Checklist ({checklist.filter((c) => c.done).length}/{checklist.length})
          </label>
          <ul className="space-y-1.5">
            {checklist.map((c, i) => (
              <li key={i} className="flex items-center gap-2 text-[13px]">
                <input
                  type="checkbox"
                  checked={c.done}
                  onChange={() => toggleCheck(i)}
                  className="h-[15px] w-[15px] accent-[var(--accent)]"
                  aria-label={`Marcar ${c.text}`}
                />
                <span className={c.done ? "text-[var(--muted)] line-through" : ""}>
                  {c.text}
                </span>
              </li>
            ))}
            {checklist.length === 0 && (
              <li className="text-[12px] text-[var(--muted)]">Sem itens.</li>
            )}
          </ul>
        </div>

        {error && (
          <p className="mt-3 rounded-[10px] bg-[var(--danger-bg)] p-2 text-sm text-[var(--danger)]" role="alert">
            {error}
          </p>
        )}

        <div className="mt-4 flex items-center justify-between gap-2 border-t border-[var(--border)] pt-3">
          <div>
            {!isNew && (
              <button
                type="button"
                onClick={remove}
                disabled={busy}
                className="rounded-[10px] px-3 py-2 text-sm font-medium text-[var(--danger)] transition-colors hover:bg-[var(--danger-bg)] disabled:opacity-40"
              >
                🗑 Excluir
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-[10px] border border-[var(--border)] px-3 py-2 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-40"
            >
              Cancelar
            </button>
            {!isNew && (
              <button
                type="button"
                onClick={run}
                disabled={busy}
                className="rounded-[10px] px-4 py-2 text-sm font-semibold text-[#06121a] transition-[filter] [background:linear-gradient(135deg,var(--accent),var(--accent-2))] hover:brightness-110 disabled:opacity-40"
              >
                ▶ Executar agente
              </button>
            )}
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="rounded-[10px] px-4 py-2 text-sm font-semibold text-[#06121a] transition-[filter] [background:linear-gradient(135deg,var(--accent),var(--accent-2))] hover:brightness-110 disabled:opacity-40"
            >
              Salvar
            </button>
          </div>
        </div>

        {!isNew && (
          <div className="mt-3">
            <label className={labelCls}>Mover para coluna</label>
            <div className="flex flex-wrap gap-1">
              {COLUMN_ORDER.map((col) => (
                <button
                  key={col}
                  type="button"
                  disabled={busy}
                  onClick={() => move(col)}
                  className="rounded-[10px] border border-[var(--border)] px-2 py-1 text-xs text-[var(--text-2)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-40"
                >
                  {COLUMN_LABELS[col]}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
