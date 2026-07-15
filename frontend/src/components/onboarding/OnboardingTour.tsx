import { useEffect, useState } from "react";

export const ONBOARDING_FLAG = "af_onboarding_done";

export function isOnboardingDone(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_FLAG) === "1";
  } catch {
    return false;
  }
}

export function markOnboardingDone(): void {
  try {
    localStorage.setItem(ONBOARDING_FLAG, "1");
  } catch {
    // localStorage indisponível: ignora (tour reaparecerá no próximo acesso).
  }
}

interface Step {
  title: string;
  body: string;
  /** Seletor do elemento da UI a destacar (highlight). Ausente = central. */
  highlight?: string;
}

const STEPS: Step[] = [
  {
    title: "Bem-vindo ao AgentFlow Studio",
    body: "Este é um board Kanban de pipeline multi-agente: cada ideia vira um Card que atravessa 6 colunas (Backlog → Researching → Planning → Reviewing → Production → Done), movido pelos agentes de IA.",
  },
  {
    title: "Crie seu primeiro card",
    body: "Clique em “+ Novo card” (coluna Backlog) para abrir o modal e descrever sua ideia. O Ideation Agent a estrutura automaticamente.",
    highlight: '[aria-label="Filtrar por fase"] ~ button, button:has(+ button)', // aproximação; fallback abaixo
  },
  {
    title: "Conductor — orquestração conversacional",
    body: "Na aba Conductor você descreve a ideia em linguagem natural e o orquestrador conduz o card pelo pipeline inteiro (Research, Planner, Reviewer, Dev) por você.",
    highlight: 'nav [aria-current="page"], nav button',
  },
  {
    title: "Dashboard de métricas",
    body: "A aba Dashboard mostra custo, taxa de auto-aprovação e tempo por fase — útil para acompanhar o gasto do seu orçamento (F-011).",
    highlight: "nav button",
  },
  {
    title: "Tema e conclusão",
    body: "Use o botão de tema na barra lateral para alternar claro/escuro. Pronto! Você pode pular este tour a qualquer momento e ele não aparecerá de novo.",
  },
];

/**
 * Tour guiado de primeiro uso (F-012 / CARD-301).
 * Persistência via localStorage (flag af_onboarding_done) — single-tenant,
 * sem migração nem endpoint novo. Ao concluir ou pular, grava a flag.
 */
export function OnboardingTour({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [skipped, setSkipped] = useState(false);
  const total = STEPS.length;
  const current = STEPS[step];

  function finish() {
    markOnboardingDone();
    onDone();
  }

  function skip() {
    setSkipped(true);
    finish();
  }

  // Teclado: Esc = pular, setas = navegar.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        skip();
      } else if (e.key === "ArrowRight") {
        if (step < total - 1) setStep((s) => s + 1);
        else finish();
      } else if (e.key === "ArrowLeft") {
        setStep((s) => Math.max(0, s - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  if (skipped) return null;

  const target =
    current.highlight
      ? (typeof document !== "undefined" &&
          document.querySelector(current.highlight)) as HTMLElement | null
      : null;
  const rect = target?.getBoundingClientRect();
  const box = rect
    ? {
        top: rect.top - 8,
        left: rect.left - 8,
        width: rect.width + 16,
        height: rect.height + 16,
      }
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label="Tour de boas-vindas"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/55" onClick={skip} />

      {/* Highlight do elemento alvo */}
      {box && (
        <div
          className="pointer-events-none absolute rounded-[12px] border-2 border-[var(--accent)] shadow-[0_0_0_4px_var(--accent-soft)]"
          style={box}
        />
      )}

      {/* Card do passo */}
      <div className="relative z-10 w-[min(420px,92vw)] rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl">
        <div className="mb-2 flex items-center justify-between">
          <span className="rounded-full bg-[var(--accent-soft)] px-2 py-0.5 text-[11px] font-semibold text-[var(--accent-text)]">
            Passo {step + 1} de {total}
          </span>
          <span className="text-[11px] text-[var(--muted)]">
            Pular (Esc)
          </span>
        </div>
        <h2 className="mb-1.5 text-[16px] font-bold">{current.title}</h2>
        <p className="text-[13px] leading-relaxed text-[var(--text-2)]">
          {current.body}
        </p>
        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={skip}
            className="rounded-[10px] px-3 py-1.5 text-[13px] text-[var(--muted)] transition-colors hover:text-[var(--text)]"
          >
            Pular tour
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                type="button"
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[13px] transition-colors hover:bg-[var(--surface-3)]"
              >
                Voltar
              </button>
            )}
            <button
              type="button"
              onClick={() => (step < total - 1 ? setStep((s) => s + 1) : finish())}
              className="rounded-[10px] px-3 py-1.5 text-[13px] font-semibold text-[#06121a] [background:linear-gradient(135deg,var(--accent),var(--accent-2))] hover:brightness-110"
            >
              {step < total - 1 ? "Próximo" : "Concluir ✓"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
