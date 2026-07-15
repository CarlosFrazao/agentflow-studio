import { useTheme } from "../../hooks/useTheme";
import { useToastStore } from "../../store/useToastStore";
import { clearToken } from "../../auth";

/**
 * Toolbar fixa na parte superior da área principal.
 * Exibe botões de ajudia, refresh, logout e troca de tema.
 * Cores via tokens (index.css) portados do HTML legado.
 */
export default function Toolbar() {
  const { theme, toggle } = useTheme();
  const push = useToastStore((state) => state.push);

  const handleRefresh = () => {
    window.location.reload();
    push({ kind: "info", title: "Página recarregada", duration: 2000 });
  };

  const handleHelp = () => {
    push({ kind: "info", title: "Ajuda: contate o suporte ou veja a documentação.", duration: 4000 });
  };

  const handleLogout = () => {
    clearToken();
    window.location.reload();
  };

  const btn =
    "rounded-[10px] border border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-1 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-3)]";

  return (
    <div className="mb-[18px] flex flex-wrap items-center gap-[10px]">
      <button onClick={handleHelp} className={btn}>
        Ajuda
      </button>
      <button onClick={handleRefresh} className={btn}>
        Recarregar
      </button>
      <button onClick={handleLogout} className={btn}>
        Logout
      </button>
      <button onClick={toggle} className={`${btn} font-medium`}>
        {theme === "dark" ? "Claro" : "Escuro"}
      </button>
    </div>
  );
}
