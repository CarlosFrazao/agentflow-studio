// AppShell – layout principal que compõe Sidebar, Toolbar e o conteúdo principal
// Visual portado do AgentFlow_Studio_Kanban_Interativo.html (tokens em index.css).

import { ReactNode, useEffect, useState } from "react";
import Sidebar from "./Sidebar";
import { useTheme } from "../../hooks/useTheme";

interface AppShellProps {
  /** Conteúdo interno da aplicação (rotas, páginas, etc.) */
  children: ReactNode;
  /** Título da view atual (topbar). */
  title: string;
  /** Subtítulo da view atual (topbar). */
  subtitle?: string;
}

function useClock(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(id);
  }, []);
  return (
    now.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) +
    " · " +
    now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function AppShell({ children, title, subtitle }: AppShellProps) {
  useTheme();
  const clock = useClock();

  return (
    <div
      className="flex h-screen w-full overflow-hidden"
      style={{ background: "var(--bg)", color: "var(--text)" }}
    >
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header
          className="flex h-[62px] shrink-0 items-center gap-[14px] border-b border-[var(--border)] bg-[var(--surface)] px-[22px]"
        >
          <div>
            <div className="text-[16px] font-semibold tracking-tight">{title}</div>
            {subtitle && (
              <div className="mt-px text-[12px] text-[var(--muted)]">
                {subtitle}
              </div>
            )}
          </div>
          <div className="flex-1" />
          <span className="rounded-[20px] border border-[var(--border)] bg-[var(--surface-2)] px-[11px] py-[5px] font-mono text-[11.5px] text-[var(--text-2)]">
            {clock}
          </span>
        </header>

        <main className="af-fade min-w-0 flex-1 overflow-y-auto p-[22px]">
          {children}
        </main>
      </div>
    </div>
  );
}
