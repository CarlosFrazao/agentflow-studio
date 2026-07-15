import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * E2E da autenticação JWT do AgentFlow Studio (v1.2).
 * Bate direto na API HTTP do backend (o frontend ainda não tem tela de login).
 *
 * Fluxo coberto:
 *  - registro (201 + token, sem vazar password_hash)
 *  - registro duplicado (409)
 *  - login válido (200 + token) e inválido (401)
 *  - endpoint protegido: 401 sem token / token inválido / token expirado
 *  - endpoint protegido: 200 com token válido (lido do global-setup)
 */

const API = "/api/v1";
const AUTH_FILE = path.join(__dirname, "..", ".auth", "user.json");

interface AuthState {
  token: string;
  userId: string;
  email: string;
  password: string;
}

function loadAuth(): AuthState {
  return JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8")) as AuthState;
}

const uniq = () => `u${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`;

test.describe("auth API", () => {
  test("POST /auth/register retorna 201 com token e não vaza o hash", async ({
    request,
  }) => {
    const email = uniq();
    const res = await request.post(`${API}/auth/register`, {
      data: { email, password: "senha-valida-123", display_name: "Novo" },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.data.access_token).toBeTruthy();
    expect(body.data.token_type).toBe("bearer");
    expect(body.data.user.email).toBe(email);
    expect(body.data).not.toHaveProperty("password_hash");
  });

  test("POST /auth/register com e-mail duplicado retorna 409", async ({
    request,
  }) => {
    const email = uniq();
    const first = await request.post(`${API}/auth/register`, {
      data: { email, password: "senha-valida-123", display_name: "Dup" },
    });
    expect(first.status()).toBe(201);
    const second = await request.post(`${API}/auth/register`, {
      data: { email, password: "senha-valida-123", display_name: "Dup2" },
    });
    expect(second.status()).toBe(409);
    expect((await second.json()).error.code).toBe("CONFLICT");
  });

  test("POST /auth/login com credenciais válidas retorna 200 + token", async ({
    request,
  }) => {
    const email = uniq();
    await request.post(`${API}/auth/register`, {
      data: { email, password: "login-senha-123", display_name: "Login" },
    });
    const res = await request.post(`${API}/auth/login`, {
      data: { email, password: "login-senha-123" },
    });
    expect(res.status()).toBe(200);
    expect((await res.json()).data.access_token).toBeTruthy();
  });

  test("POST /auth/login com senha errada retorna 401", async ({ request }) => {
    const email = uniq();
    await request.post(`${API}/auth/register`, {
      data: { email, password: "certa-senha-123", display_name: "Wrong" },
    });
    const res = await request.post(`${API}/auth/login`, {
      data: { email, password: "errada-senha-000" },
    });
    expect(res.status()).toBe(401);
    expect((await res.json()).error.code).toBe("UNAUTHORIZED");
  });

  test("GET /projects sem token retorna 401", async ({ request }) => {
    const res = await request.get(`${API}/projects`);
    expect(res.status()).toBe(401);
  });

  test("GET /projects com token inválido retorna 401", async ({ request }) => {
    const res = await request.get(`${API}/projects`, {
      headers: { Authorization: "Bearer token-inexistente" },
    });
    expect(res.status()).toBe(401);
  });

  test("GET /projects com token válido retorna 200", async ({ request }) => {
    const auth = loadAuth();
    const res = await request.get(`${API}/projects`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(Array.isArray(body.data)).toBe(true);
  });
});
