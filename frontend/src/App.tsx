import { useEffect, useState } from "react";
import { KanbanBoard } from "./components/kanban/KanbanBoard";
import { Dashboard } from "./components/dashboard/Dashboard";
import { Login } from "./components/Login";
import AppShell from "./components/layout/AppShell";
import Toolbar from "./components/layout/Toolbar";
import ToastContainer from "./components/ui/ToastContainer";
import { isLoggedIn } from "./auth";
import { useBoardStore } from "./store/useBoardStore";

const VIEW_META: Record<"kanban" | "dashboard", { title: string; subtitle: string }> = {
  kanban: { title: "Kanban de Produção", subtitle: "v1.1 · pipeline multi-agente" },
  dashboard: { title: "Dashboard de Métricas", subtitle: "v1.1 · visão geral do projeto" },
};

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  const view = useBoardStore((s) => s.view);

  useEffect(() => {
    setAuthed(isLoggedIn());
  }, []);

  if (!authed) {
    return <Login onSuccess={() => setAuthed(true)} />;
  }

  const meta = VIEW_META[view];

  return (
    <AppShell title={meta.title} subtitle={meta.subtitle}>
      <Toolbar />
      {view === "dashboard" ? <Dashboard /> : <KanbanBoard />}
      <ToastContainer />
    </AppShell>
  );
}
