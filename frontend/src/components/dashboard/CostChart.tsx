import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface CostDatum {
  label: string;
  cost_usd: number;
}

interface CostChartProps {
  title: string;
  data: CostDatum[];
  /** Largura fixa das barras quando poucos pontos; recharts auto-escala caso contrário. */
  barSize?: number;
  emptyHint?: string;
}

/**
 * Gráfico de barras de custo (reutilizável).
 * Usado tanto para a série temporal (custo por dia) quanto para custo por agente.
 * recharts traz tooltip/legenda prontos — evita SVG manual (código morto).
 */
export function CostChart({ title, data, barSize = 28, emptyHint = "Sem dados." }: CostChartProps) {
  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--text)]">{title}</h3>
      {data.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">{emptyHint}</p>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(160, data.length * 36)}>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              interval={0}
              angle={data.length > 12 ? -45 : 0}
              textAnchor={data.length > 12 ? "end" : "middle"}
              height={data.length > 12 ? 56 : 24}
              stroke="var(--border)"
            />
            <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} width={48} stroke="var(--border)" />
            <Tooltip
              formatter={(value: number) => [`$${value.toFixed(4)}`, "Custo"]}
              labelStyle={{ fontSize: 12 }}
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border-strong)",
                borderRadius: 10,
                color: "var(--text)",
                fontSize: 12,
              }}
            />
            <Bar dataKey="cost_usd" fill="var(--accent)" radius={[4, 4, 0, 0]} barSize={barSize} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
