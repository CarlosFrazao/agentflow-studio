import React from "react";
import { useTheme } from "../../hooks/useTheme";
import { useBoardStore, type BoardView } from "../../store/useBoardStore";

/**
 * Sidebar – barra de navegação lateral (visual portado do
 * AgentFlow_Studio_Kanban_Interativo.html).
 * Botão de troca de tema (light/dark) + navegação entre as views
 * (Kanban, Dashboard) via useBoardStore. "Projetos" e "Configurações"
 * ainda não têm tela própria e ficam desabilitados (sem fingir função).
 */

const NAV_ITEMS: Array<{ view: BoardView; label: string }> = [
  { view: "kanban", label: "Kanban" },
  { view: "conductor", label: "Conductor" },
  { view: "dashboard", label: "Dashboard" },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = React.useState(() => {
    const stored = localStorage.getItem("sidebar-collapsed");
    return stored === "true";
  });
  const toggleCollapse = () => {
    const newVal = !collapsed;
    setCollapsed(newVal);
    localStorage.setItem("sidebar-collapsed", newVal ? "true" : "false");
  };
  const { theme, toggle } = useTheme();
  const view = useBoardStore((s) => s.view);
  const setView = useBoardStore((s) => s.setView);

  const navClass = (active: boolean) =>
    `group relative flex w-full items-center gap-[11px] rounded-[10px] px-3 py-2 text-left text-[13.5px] font-medium outline-none transition-[background,color,transform] active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
      active
        ? "bg-[var(--accent-soft)] text-[var(--accent-text)]"
        : "text-[var(--text-2)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
    }`;

  // Indicador lateral de 3px no item ativo (skill micro-interaction-design).
  const activeBar = (active: boolean) =>
    `pointer-events-none absolute left-0 top-1/2 h-[18px] w-[3px] -translate-y-1/2 rounded-r-full bg-[var(--accent)] transition-opacity ${
      active ? "opacity-100" : "opacity-0"
    }`;

  return (
    <aside
      className={`af-sidebar relative z-30 flex h-screen shrink-0 flex-col gap-1.5 border-r border-[var(--border)] bg-[var(--surface)] px-[14px] py-[18px] transition-[transform] ${
        collapsed ? "w-16" : "w-[var(--side)]"
      }`}
    >
      {/* Brand */}
      <div
        className={`af-sidebar-center flex items-center gap-[11px] px-2 pb-4 pt-1.5 ${
          collapsed ? "justify-center" : ""
        }`}
      >
        {!collapsed && (
          <div
            className="af-sidebar-label grid h-[38px] w-[38px] shrink-0 place-items-center rounded-[11px] text-[18px] font-extrabold text-[#06121a] shadow-[0_4px_14px_-4px_var(--accent)]"
            style={{
              background:
                "linear-gradient(135deg, var(--accent), var(--accent-2))",
            }}
          >
            A
          </div>
        )}
        {!collapsed && (
          <div className="af-sidebar-label flex-1">
            <div className="text-[15px] font-bold leading-tight tracking-tight">
              AgentFlow
            </div>
            <div className="text-[11px] text-[var(--muted)]">Studio · v1.1</div>
          </div>
        )}
        <button
          onClick={toggleCollapse}
          aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
          className="group relative z-40 rounded p-1 text-[var(--text-2)] outline-none transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text)] focus-visible:ring-2 focus-visible:ring-[var(--accent)] af-sidebar-label"
        >
          <span className="inline-block transition-transform duration-200 ease-out">
            {collapsed ? "»" : "«"}
          </span>
          {collapsed && (
            <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-[8px] border border-[var(--border)] bg-[var(--surface-3)] px-2 py-1 text-[11px] font-medium text-[var(--text)] opacity-0 shadow-[var(--shadow-sm)] transition-opacity group-hover:opacity-100">
              Expandir menu
            </span>
          )}
        </button>
      </div>

      {!collapsed && (
        <div className="af-sidebar-label px-2.5 pb-1.5 pt-3 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
          Workspace
        </div>
      )}

      <nav className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.view}
            type="button"
            onClick={() => setView(item.view)}
            aria-current={view === item.view ? "page" : undefined}
            title={item.label}
            className={`${navClass(view === item.view)} af-sidebar-center`}
          >
            <span className={activeBar(view === item.view)} aria-hidden="true" />
            <span className="af-sidebar-label">{item.label}</span>
          </button>
        ))}

        <button
          type="button"
          disabled
          title="Em breve"
          className="af-sidebar-label w-full rounded-[10px] px-3 py-2 text-left text-[13.5px] text-[var(--muted)] opacity-60 cursor-not-allowed"
        >
          Projetos
        </button>
        <button
          type="button"
          disabled
          title="Em breve"
          className="af-sidebar-label w-full rounded-[10px] px-3 py-2 text-left text-[13.5px] text-[var(--muted)] opacity-60 cursor-not-allowed"
        >
          Configurações
        </button>
      </nav>

      <div className="mt-auto flex flex-col gap-2 border-t border-[var(--border)] pt-3">
        <button
          onClick={toggle}
          title={theme === "dark" ? "Tema claro" : "Tema escuro"}
          aria-label={theme === "dark" ? "Tema claro" : "Tema escuro"}
          className="af-sidebar-center flex w-full items-center gap-[10px] rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[13px] font-medium text-[var(--text-2)] outline-none transition-[background,border-color,color] hover:border-[var(--border-strong)] hover:text-[var(--text)] focus-visible:ring-2 focus-visible:ring-[var(--accent)] active:scale-[0.98]"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-[18px] w-[18px] transition-transform duration-200 ease-out"
            style={{ transform: theme === "dark" ? "rotate(180deg)" : "rotate(0deg)" }}
          >
            {theme === "dark" ? (
              <path d="M12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
            ) : (
              <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" />
            )}
          </svg>
          <span className="af-sidebar-label">{theme === "dark" ? "Tema claro" : "Tema escuro"}</span>
        </button>
        <div className="af-sidebar-center group flex items-center gap-[10px] rounded-[10px] px-2 py-1 text-[12px] text-[var(--muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-2)]">
          <div className="grid h-[28px] w-[28px] place-items-center rounded-full bg-[var(--surface-3)] text-[12px] font-bold text-[var(--text-2)] transition-colors group-hover:bg-[var(--accent-soft)] group-hover:text-[var(--accent-text)]">
            U
          </div>
          <span className="af-sidebar-label">Usuário local</span>
        </div>
      </div>
    </aside>
  );
}
