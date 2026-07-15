import { Component, type ErrorInfo, type ReactNode } from "react";
import { clearToken } from "../auth";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * Captura erros de renderização (evita tela branca) e oferece recuperação.
 * NÃO edita App.tsx — a outra IA deve envolver <App/> com este componente:
 *
 *   <ErrorBoundary><App/></ErrorBoundary>
 *
 * Também escuta "af:session-expired" (emitido por api/client.ts quando o
 * refresh falha) para mostrar o fallback de sessão expirada. O toast de
 * sessão expirada é responsabilidade da camada de UI (toolbar/toasts).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message || "Erro inesperado" };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary", error, info);
  }

  componentDidMount(): void {
    window.addEventListener("af:session-expired", this.handleSessionExpired);
  }

  componentWillUnmount(): void {
    window.removeEventListener("af:session-expired", this.handleSessionExpired);
  }

  handleSessionExpired = (): void => {
    this.setState({
      hasError: true,
      message: "Sua sessão expirou. Faça login novamente.",
    });
  };

  handleReload = (): void => {
    clearToken();
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main
          className="grid min-h-screen w-full place-items-center px-4"
          style={{ background: "var(--bg)", color: "var(--text)" }}
        >
          <div className="w-full max-w-[420px] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-6 text-center shadow-[var(--shadow)]">
            <h1 className="text-[18px] font-bold tracking-tight">
              Algo deu errado
            </h1>
            <p className="mt-2 text-[13px] text-[var(--text-2)]">{this.state.message}</p>
            <button
              type="button"
              onClick={this.handleReload}
              className="mt-5 w-full rounded-[10px] px-3 py-2.5 text-[14px] font-semibold text-[#06121a] outline-none transition-[filter,transform] [background:linear-gradient(135deg,var(--accent),var(--accent-2))] hover:brightness-110 active:scale-[0.98)]"
            >
              Entrar novamente
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
