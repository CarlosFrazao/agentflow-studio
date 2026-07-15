import { useState } from "react";
import { login } from "../auth";

/**
 * Tela de Login (FASE 4.6 — visual premium).
 * Usa os design tokens (index.css) em vez de cores hardcoded.
 * Centralização via grid place-items-center; formulário max-width 420px.
 */
export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("test@example.com");
  const [password, setPassword] = useState("test-password-123");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao entrar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      className="grid min-h-screen w-full place-items-center px-4"
      style={{ background: "var(--bg)", color: "var(--text)" }}
    >
      <form
        onSubmit={submit}
        className="af-fade w-full max-w-[420px] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-7 shadow-[var(--shadow)]"
      >
        <div className="mb-5 flex items-center gap-3">
          <div
            className="grid h-[42px] w-[42px] shrink-0 place-items-center rounded-[12px] text-[20px] font-extrabold text-[#06121a]"
            style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-2))" }}
            aria-hidden="true"
          >
            A
          </div>
          <div>
            <h1 className="text-[18px] font-bold leading-tight tracking-tight">
              AgentFlow Studio
            </h1>
            <p className="text-[12px] text-[var(--muted)]">Entre para acessar o board.</p>
          </div>
        </div>

        <label className="flex flex-col gap-1.5 text-[13px]">
          <span className="text-[var(--text-2)]">E-mail</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-[14px] text-[var(--text)] outline-none transition-colors focus:border-[var(--accent)]"
          />
        </label>

        <label className="mt-3 flex flex-col gap-1.5 text-[13px]">
          <span className="text-[var(--text-2)]">Senha</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-[14px] text-[var(--text)] outline-none transition-colors focus:border-[var(--accent)]"
          />
        </label>

        {error && (
          <p
            className="mt-3 rounded-[10px] border border-[var(--danger)] bg-[var(--danger-bg)] p-2.5 text-[13px] text-[var(--danger)]"
            role="alert"
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded-[10px] px-3 py-2.5 text-[14px] font-semibold text-[#06121a] outline-none transition-[filter,transform] [background:linear-gradient(135deg,var(--accent),var(--accent-2))] hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
        >
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
