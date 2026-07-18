import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { revertApproval } from "./client";

// Mock do fetch auth-aware: captura o path/método e devolve um envelope.
function mockFetch(body: unknown, status = 200) {
  const calls: Array<{ url: string; method: string }> = [];
  const fetchMock = vi.fn(async (url: string, opts?: RequestInit) => {
    calls.push({ url, method: opts?.method ?? "GET" });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("revertApproval (FEAT-008 G-3f)", () => {
  it("POST /cards/{id}/revert-approval e retorna reverted=true", async () => {
    const calls = mockFetch({
      success: true,
      data: { card_id: "card-1", reverted: true, column: "reviewing" },
    });

    const res = await revertApproval("card-1");

    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/cards/card-1/revert-approval");
    expect(res.reverted).toBe(true);
    expect(res.column).toBe("reviewing");
  });

  it("propaga erro 400 (janela expirada) como throw", async () => {
    mockFetch({ success: false, error: "APPROVAL_WINDOW_EXPIRED" }, 400);

    await expect(revertApproval("card-2")).rejects.toThrow();
  });
});
