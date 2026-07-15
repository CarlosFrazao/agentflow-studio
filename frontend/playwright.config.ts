import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Playwright E2E para a API de autenticação do AgentFlow Studio (v1.2).
 *
 * O `webServer` sobe o backend FastAPI num DB isolado (data/agentflow_e2e.db),
 * e o `globalSetup` registra um usuário de teste e persiste o JWT em
 * .auth/user.json (consumido pelos testes autenticados).
 *
 * Os testes batem direto na API HTTP (não há tela de login no frontend ainda),
 * o que valida o fluxo real register -> login -> acesso guardado.
 */

const API_BASE = "http://127.0.0.1:8000/api/v1";
const E2E_DB = "sqlite+aiosqlite:///./data/agentflow_e2e.db";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"]],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: API_BASE,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "api",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  globalSetup: path.join(__dirname, "e2e", "global-setup.ts"),
  webServer: {
    command: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
    cwd: path.join(__dirname, "..", "backend"),
    url: "http://127.0.0.1:8000/api/v1/health",
    timeout: 60_000,
    reuseExistingServer: false,
    env: {
      // Isolado do DB de dev: E2E usa um SQLite dedicado.
      DATABASE_URL: E2E_DB,
      ENVIRONMENT: "test",
      DEBUG: "false",
      // Secret fixo garante que o JWT emitido no global-setup seja decodificado.
      JWT_SECRET: "e2e-fixed-secret-for-tests",
      JWT_ALGORITHM: "HS256",
      ACCESS_TOKEN_TTL_MINUTES: "60",
    },
  },
});
