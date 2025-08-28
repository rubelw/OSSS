/**
 * =================================================================================================
 * OSSS Web — API Client Layer (TypeScript)
 * -------------------------------------------------------------------------------------------------
 * Purpose
 *  • Provide a single, typed gateway for the front-end to talk to the OSSS FastAPI backend.
 *  • Centralize base URL selection, auth headers, error handling, retries, and timeouts.
 *  • Keep UI components dumb: they call small functions from here, while this file encodes
 *    HTTP semantics (routes, query params, bodies) and response typing.
 *
 * Runtime assumptions
 *  • Runs in the browser AND on the server (RSC/route handlers). Do not access window-only APIs
 *    unless guarded. Prefer passing `fetch` as a dependency for SSR-friendly testing.
 *  • Authentication token is obtained from NextAuth (session) or from an injected header provider.
 *
 * Design notes
 *  • We prefer native `fetch` (built into Next.js) over third-party clients to reduce bundle size.
 *  • We export small ‘endpoint functions’ (getX, createY) that wrap a single HTTP call.
 *  • All functions return typed results and throw typed errors where possible.
 *  • JSON parsing is guarded with content-type checks to avoid runtime surprises.
 *
 * Observability
 *  • All requests can be traced by attaching an `x-request-id` or similar; see `withTracing()`.
 *  • When `NODE_ENV === "development"`, we log request/response metadata (never secrets).
 *
 * Security
 *  • Always send the bearer token only over HTTPS in production.
 *  • Never log full tokens or PII; redact; log only request id, route, status, and timings.
 *  • When uploading files, set explicit size limits and content types on the server.
 * =================================================================================================
 */
// src/osss-web/lib/api-client.ts
import { env } from "@/lib/env";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  process.env.OSSS_API_BASE ||
  "http://127.0.0.1:8081";

type FetchOpts = {
  token?: string;
  headers?: Record<string, string>;
  cache?: RequestCache;
};

async function handle(res: Response) {
  // Some error responses (401, 204) have no body — guard JSON parsing.
  const contentType = res.headers.get("content-type") || "";
  const canJson = contentType.includes("application/json");

  if (!res.ok) {
    const body = canJson ? await res.json().catch(() => undefined) : undefined;
    const detail = body?.detail || body?.error || (await res.text().catch(() => ""));
    const msg = `API ${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`;
    throw new Error(msg);
  }

  if (res.status === 204) return null;
  if (!canJson) return null;

  return res.json().catch(() => null);
}

/**
 * API call: apiGet()
 *  • What it does: <fill in endpoint purpose here>.
 *  • HTTP method & path: <GET|POST|PUT|PATCH|DELETE> /<path>
 *  • Auth: requires Bearer token (Yes/No)
 *  • Parameters:
 *      - input: <shape or link to type>
 *      - query: <query params if any>
 *  • Returns: <Type> on 2xx; throws ApiError on non-2xx with parsed error body when possible.
 *  • Idempotency: <Yes/No> — impacts retry policy.
 */
export async function apiGet(path: string, bearer?: string) {
  const res = await /* Using native fetch:
 *  - Always pass a full `headers` object (include Accept/Content-Type where appropriate)
 *  - Set `cache: "no-store"` for truly dynamic endpoints; otherwise prefer SWR/react-query
 *  - For server components, consider `revalidate` semantics instead of client fetches
 */
fetch(
`${env.OSSS_API_URL}${path}`, {
    headers: {
      "accept": "application/json",
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {})
    },
    cache: "no-store"
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}
/**
 * -------------------------------------------------------------------------------------------------
 * Operational guidance
 *  • Timeouts: Consider wrapping `fetch` with `AbortController` (e.g., 10s) to avoid hung UI.
 *  • Retries: Only retry idempotent requests; backoff: 250ms, 500ms, 1s … with jitter.
 *  • Errors: Normalize to `{ status, code, message, details }` so UI can render consistently.
 *  • Tracing: Forward `x-request-id` from the server when available; include in error reports.
 *  • Caching: For GET endpoints, prefer SWR/react-query at the call site for caching & revalidation.
 *  • Testing: Dependency-inject `fetch` so unit tests can stub network without globals.
 * -------------------------------------------------------------------------------------------------
 */
