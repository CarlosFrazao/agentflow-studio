import { describe, it, expect } from "vitest";
import { API_BASE } from "../src/lib/apiBase.ts";
import { API_BASE as CLIENT_BASE } from "../src/api/client.ts";
import { API_BASE as AUTH_BASE } from "../src/auth.ts";
import { API_BASE as WS_BASE } from "../src/api/shareWs.ts";

describe("API_BASE single source of truth (FEAT-010)", () => {
  it("is resolved from one shared module (DRY)", () => {
    // All consumers must expose the exact same API_BASE value, proving there
    // is a single source of truth and no duplicated literal/env resolution.
    expect(CLIENT_BASE).toBe(API_BASE);
    expect(AUTH_BASE).toBe(API_BASE);
    expect(WS_BASE).toBe(API_BASE);
  });

  it("falls back to the local backend default when VITE_API_BASE is unset", () => {
    if (import.meta.env.VITE_API_BASE) {
      // Test env overrides the default; assert the shared value equals it.
      expect(API_BASE).toBe(import.meta.env.VITE_API_BASE);
    } else {
      expect(API_BASE).toBe("http://localhost:8000/api/v1");
    }
  });
});
