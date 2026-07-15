import type { Toast } from "../../store/useToastStore";

/**
 * Renderiza um único toast usando as classes .toast/.toast.* do index.css
 * (tokens portados do HTML legado). Fecha ao clicar.
 */
export function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  return (
    <div
      role="alert"
      onClick={() => onDismiss(toast.id)}
      className={`toast ${toast.kind}`}
    >
      <div>
        <p className="tt">{toast.title}</p>
        {toast.detail && <p className="td">{toast.detail}</p>}
      </div>
    </div>
  );
}

export default ToastItem;
