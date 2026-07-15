import { useEffect, useState } from "react";
import { getMetricsInsights, type MetricsInsights } from "../../api/client";
import { CostChart } from "./CostChart";

const WINDOW_OPTIONS = [7, 30, 90] as const;

function RateCard({
  label,
  ratio,
  tone,
}: {
  label: string;
  ratio: number;
  tone: "good" | "warn";
}) {
  const pct = Math.round(ratio * 100);
  const color = tone === "warn" ? "text-[var(--warn)]" : "text-[var(--ok)]";
  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-sm)] transition-shadow hover:shadow-[var(--shadow)]">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color}`}>{pct}%</p>
    </div>
  );
}

/**
 * Painel de insights (Fase C1) alimentado por GET /metrics/insights.
 * Mostra custo por projeto/fase, taxa de auto-approve e reversão.
 * Estilo com tokens (index.css) portados do HTML legado.
 */
export function InsightsPanel() {
  const [data, setData] = useState<MetricsInsights | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [days, setDays] = useState<number>(30);

  useEffect(() => {
    let active = true;
    setStatus("loading");
    getMetricsInsights(days)
      .then((d) => {
        if (!active) return;
        setData(d);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [days]);

  if (status === "loading") {
    return (
      <div className="text-[var(--muted)]" role="status" aria-live="polite">
        Carregando insights…
      </div>
    );
  }

  if (status === "error" || !data) {
    return (
      <div
        className="rounded-[14px] border border-[var(--danger)] bg-[var(--danger-bg)] p-4 text-[var(--danger)]"
        role="alert"
      >
        Falha ao carregar os insights.
      </div>
    );
  }

  const projectData = Object.values(data.cost_by_project).map((p) => ({
    label: p.name,
    cost_usd: p.cost_usd,
  }));
  const phaseEntries = Object.entries(data.avg_time_per_phase).sort(
    (a, b) => b[1] - a[1],
  );

  const panel = "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-4";
  const panelTitle = "mb-3 text-sm font-semibold text-[var(--text)]";

  return (
    <section className="af-fade space-y-4" aria-label="Insights de uso e custo">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-[var(--text)]">Insights</h2>
        <div className="flex items-center gap-2">
          <label htmlFor="days" className="text-sm font-medium text-[var(--text-2)]">
            Janela
          </label>
          <select
            id="days"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] shadow-sm outline-none focus:border-[var(--accent)]"
          >
            {WINDOW_OPTIONS.map((d) => (
              <option key={d} value={d}>
                {d} dias
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <div className={panel}>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Custo no período
          </p>
          <p className="mt-1 text-2xl font-bold text-[var(--text)]">
            ${data.total_cost_usd.toFixed(2)}
          </p>
        </div>
        <RateCard label="Taxa de auto-approve" ratio={data.auto_approve_rate} tone="good" />
        <RateCard label="Taxa de reversão" ratio={data.reversal_rate} tone="warn" />
      </div>

      <CostChart
        title="Custo por projeto"
        data={projectData}
        barSize={36}
        emptyHint="Sem execuções no período."
      />

      <div className={panel}>
        <h3 className={panelTitle}>Tempo médio por fase</h3>
        {phaseEntries.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Sem execuções no período.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-[var(--muted)]">
                <tr>
                  <th className="py-2 pr-4">Fase (agente)</th>
                  <th className="py-2">Tempo médio</th>
                </tr>
              </thead>
              <tbody>
                {phaseEntries.map(([agent, ms]) => (
                  <tr key={agent} className="border-t border-[var(--border)]">
                    <td className="py-2 pr-4 text-[var(--text)]">{agent}</td>
                    <td className="py-2 text-[var(--text-2)]">{Math.round(ms)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
