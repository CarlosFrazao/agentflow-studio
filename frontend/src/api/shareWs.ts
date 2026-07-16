import type { Card, KanbanColumn } from "../types/card";
import { useBoardStore } from "../store/useBoardStore";

/**
 * Compartilhamento em tempo real via WebSocket (share_ws do backend).
 *
 * O backend transmite eventos `card.updated` (entre outros) do EventBus para
 * todos os clientes conectados em /share/{project_id}/ws. Esta função abre a
 * conexão e aplica as mudanças de card direto no useBoardStore, para que o
 * Kanban reflita o avanço disparado pelo Conductor (chat) sem refresh manual.
 */

function wsBaseFromApi(): string {
  const api = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
  // http(s)://host/api/v1 -> ws(s)://host/api/v1
  return api.replace(/^http/, "ws");
}

export interface ShareWsHandle {
  close: () => void;
}

/** Evento de tempo real de um agente (status/chunk) enviado pelo backend. */
export interface AgentEvent {
  type: "agent.status" | "agent.chunk" | "agent.turn_done";
  payload: {
    conversation_id?: string;
    project_id?: string;
    agent: string;
    status?: "start" | "done";
    label?: string;
    text?: string;
  };
}

/**
 * Abre a conexão de tempo real para um projeto.
 * @param projectId id do projeto a acompanhar
 * @param options.conversationId filtra eventos de agente por conversa (chat)
 * @param options.onStatus callback opcional de status da conexão
 * @param options.onAgentEvent callback para eventos agent.status/agent.chunk
 *   (abordagem híbrida: POST síncrono intacto + streaming de progresso no WS)
 * @returns handle com close() para limpar no unmount
 */
export function connectShareWs(
  projectId: string,
  options: {
    conversationId?: string;
    onStatus?: (status: "connecting" | "open" | "closed") => void;
    onAgentEvent?: (e: AgentEvent) => void;
  } = {},
): ShareWsHandle {
  const { conversationId, onStatus, onAgentEvent } = options;
  const qs = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  const url = `${wsBaseFromApi()}/share/${projectId}/ws${qs}`;
  let socket: WebSocket | null = null;
  let closed = false;

  const open = () => {
    if (closed) return;
    onStatus?.("connecting");
    const ws = new WebSocket(url);
    socket = ws;

    ws.onopen = () => onStatus?.("open");

    ws.onmessage = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(ev.data as string) as {
          type: string;
          payload?: Record<string, unknown>;
        };
        if (
          msg.type === "agent.status" ||
          msg.type === "agent.chunk" ||
          msg.type === "agent.turn_done"
        ) {
          onAgentEvent?.(msg as AgentEvent);
          return;
        }
        if (msg.type !== "card.updated" || !msg.payload) return;
        const p = msg.payload;
        const card = payloadToCard(p);
        if (!card) return;
        const store = useBoardStore.getState();
        const exists = store.cards.some((c) => c.id === card.id);
        if (exists) store.replaceCard(card);
        else store.setCards([...store.cards, card]);
      } catch {
        // Payload inesperado: ignora sem quebrar a conexão.
      }
    };

    ws.onclose = () => {
      onStatus?.("closed");
      // Tenta reconectar uma vez se não foi fechado voluntariamente.
      if (!closed) {
        setTimeout(open, 1500);
      }
    };

    ws.onerror = () => {
      // O onclose subsequente cuida da reconexão.
      ws.close();
    };
  };

  open();

  return {
    close: () => {
      closed = true;
      socket?.close();
      socket = null;
    },
  };
}

/** Converte o payload do evento card.updated num Card mínimo do store. */
function payloadToCard(p: Record<string, unknown>): Card | null {
  const id = p["card_id"];
  const project_id = p["project_id"];
  const column = p["column"];
  if (typeof id !== "string" || typeof project_id !== "string") return null;
  return {
    id,
    project_id,
    column: (column as KanbanColumn) ?? "backlog",
    title: typeof p["title"] === "string" ? (p["title"] as string) : "Card",
    order_index: 0,
    confidence_score:
      typeof p["confidence_score"] === "number"
        ? (p["confidence_score"] as number)
        : 0,
    approval_by: "none",
    auto_approved: Boolean(p["auto_approved"]),
    revert_deadline: null,
    meta: {},
    created_at: "",
    updated_at: "",
  };
}
