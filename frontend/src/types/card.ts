export type KanbanColumn =
  | "backlog"
  | "researching"
  | "planning"
  | "reviewing"
  | "production"
  | "done";

export interface Card {
  id: string;
  project_id: string;
  column: KanbanColumn;
  title: string;
  order_index: number;
  confidence_score: number;
  approval_by: "human" | "auto" | "none";
  auto_approved: boolean;
  revert_deadline: string | null;
  meta: CardMeta;
  created_at: string;
  updated_at: string;
}

/** Metadados ricos do card persistidos no backend (card.meta, JSON). */
export interface CardMeta {
  code?: string;
  agent?: string;
  priority?: "P0" | "P1" | "P2";
  estimate?: number;
  phase?: string;
  description?: string;
  deps?: string[];
  checklist?: Array<{ text: string; done: boolean }>;
  [key: string]: unknown;
}

export interface PaginatedCards {
  success: boolean;
  data: Card[];
  meta: {
    request_id: string;
    timestamp: string;
    pagination?: {
      total: number;
      page: number;
      per_page: number;
      total_pages: number;
    };
  };
}

export const COLUMN_LABELS: Record<KanbanColumn, string> = {
  backlog: "Backlog",
  researching: "Researching",
  planning: "Planning",
  reviewing: "Reviewing",
  production: "Production",
  done: "Done",
};

export const COLUMN_ORDER: KanbanColumn[] = [
  "backlog",
  "researching",
  "planning",
  "reviewing",
  "production",
  "done",
];
