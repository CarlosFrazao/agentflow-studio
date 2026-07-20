import { API_BASE } from "./lib/apiBase.ts";

export { API_BASE };

// FEAT-008 (B10-1): o access token NÃO vai mais para localStorage. Ele é
// persistido num cookie HttpOnly pelo backend (Set-Cookie em /auth/login) e
// enviado de volta automaticamente via `credentials: "include"` (ver client.ts).
// O frontend guarda o access token SÓ em memória: suficiente para o gate de
// UI (UX surface) e para o refresh; some ao fechar a aba (reduz XSS surface).
let accessToken: string | null = null;
// Refresh token fica APENAS em memória (não persiste): fecha aba = perde sessão.
let refreshToken: string | null = null;

export function getToken(): string | null {
  return accessToken;
}

export function setToken(token: string): void {
  accessToken = token;
}

export function clearToken(): void {
  accessToken = null;
  refreshToken = null;
}

export function isLoggedIn(): boolean {
  // Gate client-side é UX surface: o backend (cookie/Bearer) é fonte de verdade.
  return Boolean(accessToken);
}

/**
 * FEAT-008: desloga invalidando o cookie HttpOnly no backend e limpando a
 * memória do cliente. O backend expira o cookie via POST /auth/logout.
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { Accept: "application/json" },
      credentials: "include",
    });
  } catch {
    // Mesmo se a rede falhar, o cliente descarta a sessão localmente.
  } finally {
    clearToken();
  }
}

// --- refresh token (memória apenas) ---
export function getRefreshToken(): string | null {
  return refreshToken;
}

export function setRefreshToken(token: string | null): void {
  refreshToken = token;
}

export function setSession(access: string, refresh: string): void {
  setToken(access);
  setRefreshToken(refresh);
}

const USER_ID_KEY = "af_user_id";

/** Retorna o id do usuário logado (persistido em setSessionUser), ou null. */
export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}

/** Persiste o id do usuário para uso em chamadas que exigem {id}. */
export function setSessionUser(
  access: string,
  refresh: string,
  userId: string,
): void {
  setSession(access, refresh);
  localStorage.setItem(USER_ID_KEY, userId);
}

interface AuthResult {
  access_token: string;
  refresh_token: string;
  user: { id: string; email: string; display_name: string };
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResult> {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) {
    throw new Error(resp.status === 401 ? "Credenciais inválidas" : `HTTP ${resp.status}`);
  }
  const json = (await resp.json()) as { data: AuthResult };
  setSessionUser(json.data.access_token, json.data.refresh_token, json.data.user.id);
  return json.data;
}

export async function refreshAccessToken(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const resp = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${rt}`,
      },
    });
    if (!resp.ok) return false;
    const json = (await resp.json()) as {
      data: { access_token: string; refresh_token: string };
    };
    setSession(json.data.access_token, json.data.refresh_token);
    return true;
  } catch {
    return false;
  }
}
