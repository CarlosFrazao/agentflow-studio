/**
 * Single source of truth for the API base URL.
 *
 * Consumed by client.ts, auth.ts and shareWs.ts so the Vite env override
 * (VITE_API_BASE) is resolved in exactly one place (DRY). Defaults to the
 * local FastAPI backend at http://localhost:8000/api/v1.
 */
export const API_BASE: string =
  import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
