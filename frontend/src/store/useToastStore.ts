import { create } from "zustand";

export type ToastKind = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  kind: ToastKind;
  title: string;
  detail?: string;
  /** ms até auto-dismiss; 0 = não some sozinho. */
  duration: number;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id"> & { id?: string }) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const timers = new Map<string, ReturnType<typeof setTimeout>>();

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (toast) => {
    const id = toast.id ?? `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const duration = toast.duration ?? 4000;
    set((s) => ({ toasts: [...s.toasts.filter((t) => t.id !== id), { ...toast, id, duration }] }));
    if (duration > 0) {
      const prev = timers.get(id);
      if (prev) clearTimeout(prev);
      timers.set(
        id,
        setTimeout(() => get().dismiss(id), duration),
      );
    }
    return id;
  },
  dismiss: (id) => {
    const t = timers.get(id);
    if (t) {
      clearTimeout(t);
      timers.delete(id);
    }
    set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }));
  },
  clear: () => {
    timers.forEach((t) => clearTimeout(t));
    timers.clear();
    set({ toasts: [] });
  },
}));

/** Helpers ergonômicos para uso fora de componentes (ex: catch de API). */
export const toast = {
  success: (title: string, detail?: string) =>
    useToastStore.getState().push({ kind: "success", title, detail, duration: 4000 }),
  error: (title: string, detail?: string) =>
    useToastStore.getState().push({ kind: "error", title, detail, duration: 6000 }),
  info: (title: string, detail?: string) =>
    useToastStore.getState().push({ kind: "info", title, detail, duration: 4000 }),
  warning: (title: string, detail?: string) =>
    useToastStore.getState().push({ kind: "warning", title, detail, duration: 5000 }),
};
