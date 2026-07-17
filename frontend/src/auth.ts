import { API_BASE } from "./lib/apiBase.ts";

export { API_BASE };

const TOKEN_KEY = "af_token";
// Refresh token fica APENAS em memória (não persiste): fecha aba = perde sessão.
// Reduz superfície de XSS (não vai para localStorage).
let refreshToken: string | null = null;

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  refreshToken = null;
}

export function isLoggedIn(): boolean {
  return Boolean(getToken());
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
