import type { Message } from "../../types/conductor";

const TOOL_LABELS: Record<string, string> = {
  run_ideation: "Ideation Agent",
  run_research: "Research Agent",
  run_code_research: "Code Research Agent",
  run_planner: "Planner Agent",
  run_reviewer: "Reviewer Agent",
  run_dev: "Dev Agent",
  get_card_state: "Card State",
};

function toolSummary(msg: Message): string {
  const out = msg.tool_output ?? {};
  if (msg.tool_name === "run_research") {
    return `Research Agent concluído (confiança ${(out.confidence ?? 0)})`;
  }
  if (msg.tool_name === "run_code_research") {
    const n = Array.isArray(out.suggestions) ? (out.suggestions as unknown[]).length : 0;
    return `Code Research concluído (${n} sugestões)`;
  }
  if (msg.tool_name === "run_ideation") {
    return `Ideation: ${String(out.project_name ?? "projeto")} estruturado`;
  }
  if (msg.tool_name === "run_planner") {
    return "Planner Agent concluído";
  }
  if (msg.tool_name === "run_reviewer") {
    const crit = Number(out.critical_count ?? 0);
    return `Reviewer concluído (${crit} alertas críticos)`;
  }
  if (msg.tool_name === "run_dev") {
    return out.sandbox_success ? "Dev Agent concluído" : "Dev Agent (validação pendente)";
  }
  return TOOL_LABELS[msg.tool_name ?? ""] ?? msg.tool_name ?? "tool";
}

export function ChatMessage({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--accent)] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-white shadow-[var(--shadow-sm)]">
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.role === "tool") {
    return (
      <div className="flex justify-start">
        <div className="flex max-w-[88%] items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[12px] text-[var(--text-2)]">
          <span aria-hidden="true">🔧</span>
          <span className="font-medium text-[var(--text)]">
            {toolSummary(msg)}
          </span>
        </div>
      </div>
    );
  }

  // conductor
  return (
    <div className="flex justify-start">
      <div
        role="status"
        className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--surface)] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-[var(--text)] shadow-[var(--shadow-sm)]"
      >
        {msg.content}
      </div>
    </div>
  );
}
