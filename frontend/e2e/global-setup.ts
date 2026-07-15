import { request, type FullConfig } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Registra um usuário de teste e persiste o JWT recebido em .auth/user.json.
 * Os testes autenticados leem esse storage state para montar o Bearer token.
 */

const API_BASE = "http://127.0.0.1:8000/api/v1";
const AUTH_FILE = path.join(__dirname, "..", ".auth", "user.json");

const TEST_EMAIL = "e2e-user@example.com";
const TEST_PASSWORD = "e2e-password-123";
const TEST_NAME = "E2E User";

async function globalSetup(config: FullConfig): Promise<void> {
  const apiRequest = await request.newContext();
  try {
    // Garante um usuário limpo a cada run (idempotência do lado do servidor:
    // se já existir, registra um novo com sufixo de timestamp).
    const email = TEST_EMAIL;
    const reg = await apiRequest.post(`${API_BASE}/auth/register`, {
      data: { email, password: TEST_PASSWORD, display_name: TEST_NAME },
    });

    let token: string;
    let userId: string;
    if (reg.ok()) {
      const body = await reg.json();
      token = body.data.access_token;
      userId = body.data.user.id;
    } else {
      // 409 = já existe; faz login em vez de registrar.
      const login = await apiRequest.post(`${API_BASE}/auth/login`, {
        data: { email, password: TEST_PASSWORD },
      });
      if (!login.ok()) {
        throw new Error(
          `Falha ao obter credenciais E2E: register=${reg.status()} login=${login.status()}`,
        );
      }
      const body = await login.json();
      token = body.data.access_token;
      userId = body.data.user.id;
    }

    fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
    fs.writeFileSync(
      AUTH_FILE,
      JSON.stringify({ token, userId, email, password: TEST_PASSWORD }, null, 2),
      "utf-8",
    );
    console.log(`[global-setup] token E2E salvo para ${email} (user ${userId})`);
  } finally {
    await apiRequest.dispose();
  }
}

export default globalSetup;
