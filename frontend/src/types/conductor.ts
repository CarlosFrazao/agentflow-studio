export type ConductorRole = "user" | "conductor" | "tool";

export interface ConversationCreate {
  project_id: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  card_id: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: ConductorRole;
  content: string;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: Record<string, unknown> | null;
}

export interface ConversationMessages {
  conversation: Conversation;
  messages: Message[];
}

export interface ConductorTurnRequest {
  content: string;
}

export interface ConductorToolCall {
  tool: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
}

export interface ConductorTurn {
  conversation_id: string;
  conductor_reply: string;
  tool_calls: ConductorToolCall[];
  card_id: string | null;
  awaiting_user: boolean;
}
