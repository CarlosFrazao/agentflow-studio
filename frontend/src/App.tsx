import { useEffect, useState } from "react";
import { KanbanBoard } from "./components/kanban/KanbanBoard";
import { Dashboard } from "./components/dashboard/Dashboard";
import { ChatPanel } from "./components/conductor/ChatPanel";
import { Login } from "./components/Login";
import AppShell from "./components/layout/AppShell";
import Toolbar from "./components/layout/Toolbar";
import ToastContainer from "./components/ui/ToastContainer";
import { OnboardingTour, isOnboardingDone } from "./components/onboarding/OnboardingTour";
import { isLoggedIn } from "./auth";
import { useBoardStore } from "./store/useBoardStore";

const VIEW_META: Record<
  "kanban" | "dashboard" | "conductor",
  { title: string; subtitle: string }
> = {
  kanban: { title: "Kanban de Produção", subtitle: "v1.1 · pipeline multi-agente" },
  conductor: { title: "Conductor", subtitle: "v1.3 · orquestração conversacional" },
  dashboard: { title: "Dashboard de Métricas", subtitle: "v1.1 · visão geral do projeto" },
};

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  const [showTour, setShowTour] = useState(false);
  const view = useBoardStore((s) => s.view);

  useEffect(() => {
    setAuthed(isLoggedIn());
  }, []);

  // Ao logar, abre o tour de primeiro uso se ainda não foi concluído (F-012).
  useEffect(() => {
    if (authed && !isOnboardingDone()) {
      setShowTour(true);
    }
  }, [authed]);

  if (!authed) {
    return <Login onSuccess={() => setAuthed(true)} />;
  }

  const meta = VIEW_META[view];

  return (
    <AppShell title={meta.title} subtitle={meta.subtitle}>
      <Toolbar />
      {view === "dashboard" ? (
        <Dashboard />
      ) : view === "conductor" ? (
        <ChatPanel />
      ) : (
        <KanbanBoard />
      )}
      <ToastContainer />
      {showTour && <OnboardingTour onDone={() => setShowTour(false)} />}
    </AppShell>
  );
}

