import { env } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";
import { ApiError } from "./errors";

type Query = Record<string, string | number | undefined | null>;
type Method = "GET" | "POST" | "PATCH";

// A free backend instance needs about a minute to wake up.
const TIMEOUT_MS = 75_000;

async function accessToken(refresh = false) {
  const auth = supabaseBrowser().auth;
  const { data } = refresh ? await auth.refreshSession() : await auth.getSession();
  return data.session?.access_token ?? null;
}

function toLogin() {
  const next = encodeURIComponent(window.location.pathname);
  // a full load on purpose: it drops every cached record of the ended session
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?reason=expired&next=${next}`);
}

async function send(method: Method, path: string, query: Query | undefined, body: unknown, token: string | null) {
  const url = new URL(`${env.apiBaseUrl}/api/v1${path}`);
  Object.entries(query ?? {}).forEach(([k, v]) => v != null && v !== "" && url.searchParams.set(k, String(v)));
  const form = body instanceof FormData;
  return fetch(url, {
    method,
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
    headers: {
      "X-Request-ID": crypto.randomUUID(),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body !== undefined && !form ? { "Content-Type": "application/json" } : {}),
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
}

async function failure(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  const error = body?.error;
  return new ApiError(response.status, error?.code ?? "HTTP_ERROR", error?.message ?? `The server answered ${response.status}.`,
    error?.details ?? [], error?.request_id ?? response.headers.get("x-request-id"));
}

/** One request. Only GET is repeated after a network failure or 503, because it changes nothing. */
async function request<T>(method: Method, path: string, query?: Query, body?: unknown): Promise<T> {
  let token = await accessToken();
  const attempts = method === "GET" ? 2 : 1;
  for (let attempt = 1; ; attempt++) {
    let response: Response;
    try {
      response = await send(method, path, query, body, token);
    } catch (error) {
      if (attempt < attempts) continue;
      const slow = error instanceof DOMException && error.name === "TimeoutError";
      throw new ApiError(0, slow ? "TIMEOUT" : "NETWORK", slow
        ? "The planning service took too long to answer." : "The planning service cannot be reached.");
    }
    if (response.ok) return (response.status === 204 ? undefined : await response.json()) as T;
    if (response.status === 401) {
      const renewed = await accessToken(true);
      if (renewed && renewed !== token) {
        token = renewed;
        response = await send(method, path, query, body, token);
        if (response.ok) return (response.status === 204 ? undefined : await response.json()) as T;
      }
      if (response.status === 401) toLogin();
    }
    if (response.status === 503 && attempt < attempts) continue;
    throw await failure(response);
  }
}

export const http = {
  get: <T,>(path: string, query?: Query) => request<T>("GET", path, query),
  post: <T,>(path: string, body?: unknown, query?: Query) => request<T>("POST", path, query, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, undefined, body),
};
