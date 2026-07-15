import { apiGet, apiSend, type Envelope } from "./client";
import type {
  Conversation,
  ConversationCreate,
  ConversationMessages,
  ConductorTurn,
  ConductorTurnRequest,
  Message,
} from "../types/conductor";

/** Cria uma nova conversa atrelada a um projeto (Plano F-023 §4). */
export async function createConversation(
  input: ConversationCreate,
): Promise<Conversation> {
  const r = await apiSend<Envelope<Conversation>>(
    "POST",
    "/conversations",
    input,
  );
  return r.data;
}

/** Envia uma mensagem e roda um turno do Conductor. */
export async function sendConductorMessage(
  conversationId: string,
  content: string,
): Promise<ConductorTurn> {
  const r = await apiSend<Envelope<ConductorTurn>>(
    "POST",
    `/conversations/${conversationId}/messages`,
    { content } satisfies ConductorTurnRequest,
  );
  return r.data;
}

/** Retorna o histórico completo de uma conversa. */
export async function listConversationMessages(
  conversationId: string,
): Promise<ConversationMessages> {
  const r = await apiGet<Envelope<ConversationMessages>>(
    `/conversations/${conversationId}/messages`,
  );
  return r.data;
}

export type { Message };
