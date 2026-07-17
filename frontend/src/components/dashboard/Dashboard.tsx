import { useEffect, useState } from "react";
import { getDashboard, type DashboardData } from "../../api/dashboard";
import { listProjects } from "../../api/client";
import { CostChart } from "./CostChart";
import { InsightsPanel } from "./InsightsPanel";
import { PreferencesGraph } from "../preferences/PreferencesGraph";

interface ProjectOption {
  id: string;
  name: string;
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="relative overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-[18px]">
      <p className="text-[12px] uppercase tracking-[0.05em] text-[var(--muted)]">{label}</p>
      <p className="mt-1.5 text-[27px] font-bold font-mono tracking-tight text-[var(--text)]">
        {value}
      </p>
      {sub && <p className="mt-1 text-[11.5px] text-[var(--text-2)]">{sub}</p>}
    </div>
  );
}

const STATUS_BADGE: Record<string, string> = {
  success: "bg-[var(--ok)_14%] text-[var(--ok)]",
  failed: "bg-[var(--danger)_14%] text-[var(--danger)]",
  running: "bg-[var(--warn)_14%] text-[var(--warn)]",
  pending: "bg-[var(--surface-3)] text-[var(--text-2)]",
};

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [projectId, setProjectId] = useState<string>("");

  useEffect(() => {
    void listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    setStatus("loading");
    getDashboard(projectId || undefined)
      .then((d) => {
        setData(d);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [projectId]);

  if (status === "loading") {
    return (
      <div className="text-[var(--muted)]" role="status" aria-live="polite">
        Carregando métricas…
      </div>
    );
  }

  if (status === "error" || !data) {
    return (
      <div className="rounded-[14px] border border-[var(--danger)] bg-[var(--danger-bg)] p-4 text-[var(--danger)]" role="alert">
        Falha ao carregar o dashboard.
      </div>
    );
  }

  const pct = Math.round(data.spend_vs_limit.ratio * 100);
  const barColor =
    data.spend_vs_limit.ratio >= 1
      ? "var(--danger)"
      : data.spend_vs_limit.ratio >= 0.8
        ? "var(--warn)"
        : "var(--ok)";

  const dayData = data.cost_by_day.map((d) => ({
    label: d.date.slice(5),
    cost_usd: d.cost_usd,
  }));
  const agentData = data.cost_by_agent.map((a) => ({
    label: a.agent_name,
    cost_usd: a.cost_usd,
  }));
  const statusEntries = Object.entries(data.executions_by_status).sort((a, b) => b[1] - a[1]);

  const panel = "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-[18px_20px]";
  const panelTitle = "m-0 mb-1 text-[14px] font-semibold text-[var(--text)]";

  return (
    <section className="af-fade space-y-4">
      <div className="flex items-center gap-3">
        <label htmlFor="proj" className="text-sm font-medium text-[var(--text-2)]">
          Projeto
        </label>
        <select
          id="proj"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] shadow-sm outline-none focus:border-[var(--accent)]"
        >
          <option value="">Todos</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {/* Stats */}
      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
        <Stat label="Projetos" value={String(data.projects_created)} />
        <Stat label="Cards concluídos" value={String(data.cards_done)} />
        <Stat label="Custo total" value={`$${data.total_cost_usd.toFixed(2)}`} />
        <Stat label="Gasto vs limite" value={`${pct}%`} />
      </div>

      {/* Orçamento */}
      <div className={panel}>
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-[var(--text)]">Orçamento mensal</span>
          <span className="text-[var(--text-2)]">
            ${data.spend_vs_limit.spent_usd.toFixed(2)} / $
            {data.spend_vs_limit.limit_usd.toFixed(2)}
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-2)]">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${Math.min(pct, 100)}%`, background: barColor }}
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CostChartByDay data={dayData} />
        <CostChartByAgent data={agentData} />
      </div>

      <InsightsPanel />

      <PreferencesGraph />

      <div className={panel}>
        <h3 className={panelTitle}>Execuções por status</h3>
        {statusEntries.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Nenhuma execução ainda.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {statusEntries.map(([st, count]) => (
              <span
                key={st}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  STATUS_BADGE[st] ?? "bg-[var(--surface-3)] text-[var(--text-2)]"
                }`}
              >
                {st}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className={panel}>
        <h3 className={panelTitle}>Execuções recentes</h3>
        {data.recent_executions.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Nenhuma execução ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-[0.05em] text-[var(--muted)]">
                <tr>
                  <th className="py-2 pr-4">Agente</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Duração</th>
                  <th className="py-2">Custo</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_executions.map((e) => (
                  <tr key={e.id} className="border-t border-[var(--border)]">
                    <td className="py-2 pr-4 text-[var(--text)]">{e.agent_name}</td>
                    <td className="py-2 pr-4 text-[var(--text-2)]">{e.status}</td>
                    <td className="py-2 pr-4 text-[var(--text-2)]">{e.duration_ms} ms</td>
                    <td className="py-2 font-mono text-[var(--text-2)]">${e.cost_usd.toFixed(4)}</td>
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

function CostChartByDay({ data }: { data: Array<{ label: string; cost_usd: number }> }) {
  return <CostChart title="Custo por dia (30 dias)" data={data} emptyHint="Sem execuções com data." />;
}

function CostChartByAgent({ data }: { data: Array<{ label: string; cost_usd: number }> }) {
  return <CostChart title="Custo por agente" data={data} barSize={36} emptyHint="Sem execuções." />;
}
