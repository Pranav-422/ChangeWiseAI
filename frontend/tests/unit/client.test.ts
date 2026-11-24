import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), refreshSession: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({ supabaseBrowser: () => ({ auth }) }));
vi.mock("@/lib/env", () => ({ env: { apiBaseUrl: "http://api.test", supabaseUrl: "", supabaseKey: "" }, configured: true }));
import { http } from "@/lib/api/client";

const answer = (status: number, body: unknown = {}) => new Response(JSON.stringify(body), { status });
const error = (code: string, message = "m") => ({ error: { code, message, details: [{ field: "a", message: "b" }], request_id: "r1" } });
const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  auth.getSession.mockResolvedValue({ data: { session: { access_token: "t1" } } });
  auth.refreshSession.mockResolvedValue({ data: { session: null } });
});
afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("sends the token, a request ID and the query", async () => {
    fetchMock.mockResolvedValue(answer(200, { ok: 1 }));
    expect(await http.get("/x", { scenario: "base", empty: "", none: null })).toEqual({ ok: 1 });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toBe("http://api.test/api/v1/x?scenario=base");
    expect(init.headers.Authorization).toBe("Bearer t1");
    expect(init.headers["X-Request-ID"]).toMatch(/[0-9a-f-]{36}/);
    expect(init.cache).toBe("no-store");
  });
  it("turns the error body into one error type", async () => {
    fetchMock.mockResolvedValue(answer(409, error("DECISION_REFUSED", "Already decided")));
    await expect(http.post("/x", {})).rejects.toMatchObject({ status: 409, code: "DECISION_REFUSED", message: "Already decided", requestId: "r1", details: [{ field: "a" }] });
  });
  it("survives a reply that is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>", { status: 502 }));
    await expect(http.post("/x")).rejects.toMatchObject({ status: 502, code: "HTTP_ERROR" });
  });
  it("repeats a failed read once and a write never", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("net")).mockResolvedValueOnce(answer(200, 1));
    expect(await http.get("/x")).toBe(1);
    fetchMock.mockReset().mockRejectedValue(new TypeError("net"));
    await expect(http.post("/x", {})).rejects.toMatchObject({ code: "NETWORK" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("repeats a read after 503", async () => {
    fetchMock.mockResolvedValueOnce(answer(503, error("DATABASE_UNAVAILABLE"))).mockResolvedValueOnce(answer(200, 2));
    expect(await http.get("/x")).toBe(2);
  });
  it("reports a timeout as a timeout", async () => {
    fetchMock.mockRejectedValue(new DOMException("slow", "TimeoutError"));
    await expect(http.post("/x")).rejects.toMatchObject({ code: "TIMEOUT" });
  });
  it("renews an expired token once and repeats the call with it", async () => {
    auth.refreshSession.mockResolvedValue({ data: { session: { access_token: "t2" } } });
    fetchMock.mockResolvedValueOnce(answer(401, error("UNAUTHENTICATED"))).mockResolvedValueOnce(answer(200, 3));
    expect(await http.get("/x")).toBe(3);
    expect(fetchMock.mock.calls[1]![1].headers.Authorization).toBe("Bearer t2");
  });
  it("does not set a JSON type on a file upload", async () => {
    fetchMock.mockResolvedValue(answer(200));
    await http.post("/x", new FormData());
    expect(fetchMock.mock.calls[0]![1].headers["Content-Type"]).toBeUndefined();
  });
});
