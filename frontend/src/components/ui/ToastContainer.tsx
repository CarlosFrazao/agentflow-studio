import { useToastStore } from "../../store/useToastStore";
import ToastItem from "./Toast";

/**
 * Lista de toasts no canto inferior direito (estilo .toasts do index.css).
 * Cada toast desaparece automaticamente ou ao ser clicado.
 */
export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div className="toasts">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
      ))}
    </div>
  );
}

export default ToastContainer;
