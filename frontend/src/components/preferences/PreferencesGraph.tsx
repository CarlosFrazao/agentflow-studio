import { useEffect, useState } from "react";
import { getPreferenceGraph, type PreferenceGraph as Graph } from "../../api/client";
import { getUserId } from "../../auth";

/**
 * Grafo de preferências aprendidas (Fase D1 / F-010 §5).
 *
 * Consome GET /users/{id}/preferences/graph e desenha nós + arestas em SVG
 * (sem dependência nova). Estados loading/erro acessíveis (role=status/alert)
 * e cleanup de efeito (flag `active`) para evitar setState após unmount.
 */
export function PreferencesGraph() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");

  useEffect(() => {
    let active = true;
    const userId = getUserId();
    if (!userId) {
      setStatus("error");
      return;
    }
    setStatus("loading");
    getPreferenceGraph(userId)
      .then((g) => {
        if (!active) return;
        setGraph(g);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("error");
      });
    return () => {
      active = false;
    };
  }, []);

  if (status === "loading") {
    return (
      <div className="text-[var(--muted)]" role="status" aria-live="polite">
        Carregando preferências aprendidas…
      </div>
    );
  }

  if (status === "error" || !graph) {
    return (
      <div
        className="rounded-[14px] border border-[var(--danger)] bg-[var(--danger-bg)] p-4 text-[var(--danger)]"
        role="alert"
      >
        Não foi possível carregar o grafo de preferências.
      </div>
    );
  }

  const panel = "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-4";
  const panelTitle = "mb-3 text-sm font-semibold text-[var(--text)]";
  const nodeCount = graph.nodes.length;

  return (
    <section className="af-fade space-y-4" aria-label="Grafo de preferências aprendidas">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-[var(--text)]">Preferências aprendidas</h2>
        <span className="text-xs text-[var(--muted)]">
          {nodeCount} nós · {graph.edges.length} arestas
        </span>
      </div>

      {nodeCount === 0 ? (
        <p className="text-sm text-[var(--muted)]">
          Nenhuma preferência aprendida ainda.
        </p>
      ) : (
        <div className={panel}>
          <h3 className={panelTitle}>Grafo de aprendizado</h3>
          <GraphCanvas graph={graph} />
        </div>
      )}

      <div className={panel}>
        <h3 className={panelTitle}>Estatísticas</h3>
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <Stat label="Nós" value={String(graph.stats.nodes)} />
          <Stat label="Arestas" value={String(graph.stats.edges)} />
          <Stat label="Aplicadas" value={String(graph.stats.applied_nodes)} />
          <Stat label="Arquivadas" value={String(graph.stats.archived_nodes)} />
          <Stat label="Conectadas" value={String(graph.stats.linked_nodes)} />
          <Stat label="Isoladas" value={`${Math.round(graph.stats.isolated_pct * 100)}%`} />
          <Stat label="Arestas/nó" value={graph.stats.edges_per_node.toFixed(2)} />
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-[var(--text)]">{value}</p>
    </div>
  );
}

/**
 * Desenha nós em círculo + arestas como linhas. Sem libs externas.
 * Usa viewBox 0..100 para escalar de forma fluida; nós > 12 mantêm o mesmo
 * layout (círculo), apenas mais densos — mantém o componente autocontido.
 */
function GraphCanvas({ graph }: { graph: Graph }) {
  const W = 100;
  const nodes = graph.nodes;
  const radius = 42;
  const cx = 50;
  const cy = 50;
  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    pos.set(n.id, {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    });
  });

  return (
    <svg
      viewBox={`0 0 ${W} ${W}`}
      className="h-auto w-full max-w-[420px]"
      role="img"
      aria-label={`Grafo com ${nodes.length} preferências e ${graph.edges.length} conexões`}
    >
      {graph.edges.map((e, i) => {
        const a = pos.get(e.source);
        const b = pos.get(e.target);
        if (!a || !b) return null;
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="var(--border)"
            strokeWidth={0.6}
          />
        );
      })}
      {nodes.map((n) => {
        const p = pos.get(n.id)!;
        return (
          <g key={n.id}>
            <circle
              cx={p.x}
              cy={p.y}
              r={n.archived ? 2 : 3}
              fill={n.archived ? "var(--surface-3)" : "var(--accent)"}
            />
            <text
              x={p.x}
              y={p.y - 4}
              fontSize={2.6}
              textAnchor="middle"
              fill="var(--text-2)"
            >
              {n.value.length > 10 ? n.value.slice(0, 9) + "…" : n.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
