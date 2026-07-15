import type { Card, PaginatedCards } from "../types/card";
import { apiGet } from "./client";

export interface DashboardData {
  projects_created: number;
  cards_done: number;
  total_cost_usd: number;
  spend_vs_limit: { spent_usd: number; limit_usd: number; ratio: number };
  recent_executions: Array<{
    id: string;
    card_id: string;
    agent_name: string;
    status: string;
    duration_ms: number;
    cost_usd: number;
  }>;
  cost_by_day: Array<{ date: string; cost_usd: number }>;
  cost_by_agent: Array<{ agent_name: string; cost_usd: number; exec_count: number }>;
  executions_by_status: Record<string, number>;
}

export async function getDashboard(projectId?: string): Promise<DashboardData> {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const json = await apiGet<{ success: boolean; data: DashboardData }>(
    `/dashboard${qs}`,
  );
  return json.data;
}

export type { Card, PaginatedCards };
