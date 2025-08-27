/**
 * =================================================================================================
 * OSSS Web — Home Page (Client Component)
 * -------------------------------------------------------------------------------------------------
 * Purpose
 *  • Minimal front-end that exercises the auth/session pipeline and proxies to the FastAPI backend.
 *  • Renders a small dashboard with:
 *      - Auth buttons (sign in/out) via NextAuth
 *      - Backend `/healthz` status (through Next rewrites to FastAPI)
 *      - A "Session Debug" panel useful during integration
 *
 * Rendering model
 *  • This is a **Client Component** (`"use client"`), so it can use React state/effects and
 *    NextAuth’s `useSession()` hook. Avoid server-only APIs (fs, process.env secrets) here.
 *
 * Data flow
 *  • `useSession()` gives us the current session or loading/authenticated state.
 *  • `fetchJSON()` is a tiny helper to GET JSON (no caching, same-origin credentials).
 *  • `useEffect(...)` performs a one-time prefetch of backend health on mount.
 *  • `useMemo(...)` builds a compact object that is easy to inspect in the debug panel.
 *
 * Hardening tips
 *  • If you render user-provided data, sanitize it (not needed here; only JSON stringify is used).
 *  • For larger apps, prefer a data-fetching library (SWR/React Query) for caching & retries.
 *  • Consider feature-flagging the debug panel in production builds.
 * =================================================================================================
 */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { AuthButtons } from "@/components/AuthButtons";

/**
 * Health
 *  • Shape of the backend health response (very small contract).
 *  • `status` is typically "ok"/"healthy" (string to keep it flexible).
 *  • Optional `realm` may be returned by the backend (e.g., Keycloak realm or app realm id).
 *  • `null` means we haven't fetched or the request failed (we fallback to `{ status: "unknown" }`).
 */
type Health = { status: string; realm?: string } | null;


/**
 * Page(): top-level route component
 *  • Runs on the client; can access `window`, manage state, and call `useSession()`.
 *  • No props are required since this is the root index page.
 */
export default function Page() {

  // --- Authentication state -------------------------------------------------------------------
// `useSession` returns { data, status } where:
//   - status: "loading" | "authenticated" | "unauthenticated"
//   - data:   `Session | null` (contains `session.user` and any custom fields you attached)
// We derive a `loggedIn` boolean to simplify conditional UI.
const { data: session, status } = useSession();

  // True when NextAuth indicates the session is fully authenticated.
const loggedIn = status === "authenticated";


  // --- Local state ---------------------------------------------------------------------------
// `health`: last-known backend health response (or null before/if fetch fails).
// Using local component state is fine here because the value is specific to this page.
const [health, setHealth] = useState<Health>(null);


  // --- Network helper ------------------------------------------------------------------------
// `fetchJSON<T>`: small wrapper over `fetch` that:
//   • Requests JSON by sending `accept: application/json`
//   • Disables HTTP cache (`cache: "no-store"`) so development changes show immediately
//   • Sends same-origin credentials; if your backend uses cookies for auth, include them
//   • Throws on non-2xx (so callers can `catch` and handle failures uniformly)
// The generic `<T>` lets callers assert the expected JSON shape for better type hints.
const fetchJSON = useCallback(async <T,>(url: string) => {
    const res = await fetch(url, {
      headers: { accept: "application/json" },
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return (await res.json()) as T;
  }, []);


  // Prefetch backend health (once)
  // --- Side effect: prefetch backend health ---------------------------------------------------
// Runs once on mount (dependency: stable `fetchJSON`). This pattern avoids double fetches in
// development's strict mode because the function identity is memoized via useCallback([]).
// On success: updates `health`. On failure: leaves `health` as null (render shows "unknown").
useEffect(() => {
    fetchJSON<Health>("/api/osss/healthz")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, [fetchJSON]);


  // --- Derived view model ---------------------------------------------------------------------
// `sessionDebug` collects a few session facts for display (useful during integration):
//   • `status` and `loggedIn` for quick state insight
//   • `user` baseline info
//   • `hasAccessToken`: whether your auth wiring attached a token to the session
// Memoized so the object identity only changes when its inputs change, which reduces
// unnecessary re-renders of the debug panel.
const sessionDebug = useMemo(
    () => ({
      status,
      loggedIn,
      user: session?.user ?? null,
      hasAccessToken: Boolean((session as any)?.accessToken),
    }),
    [status, loggedIn, session]
  );


return (
    <div className="container">
      {/* Top bar with Auth buttons */}
      {/* --------------------------------------------------------------------------
    Top bar: product title + authentication controls
    `AuthButtons` should render Sign In / Sign Out depending on session state.
   -------------------------------------------------------------------------- */}
<div className="flex items-center justify-between mb-6">
        <h1>OSSS Web</h1>
        <AuthButtons />
      </div>

      {/* Short blurb about the integration approach */}
<p className="text-muted-foreground">
        Minimal frontend talking to the OSSS FastAPI backend via Next.js API
        routes with bearer auth.
      </p>

      {/* Card UI wrapper (visual grouping). Consider extracting a <Card> component if reused. */}
<div className="card">
        <h2>Backend Health</h2>
        <pre>{JSON.stringify(health ?? { status: "unknown" }, null, 2)}</pre>
      </div>

      {/* Optional debug panel */}
      {/* Card UI wrapper (visual grouping). Consider extracting a <Card> component if reused. */}
<div className="card">
        <h2>Session Debug</h2>
        <pre>{JSON.stringify(sessionDebug, null, 2)}</pre>
      </div>
    </div>
  );
}

/**
 * -------------------------------------------------------------------------------------------------
 * Operational guidance
 *  • If backend health is critical to page UX, add a small retry/backoff or a manual refresh button.
 *  • Consider hiding the debug panel in production to reduce bundle size (or guard via env flag).
 *  • For authenticated backend calls, forward the session’s bearer token from an API route rather
 *    than calling the backend directly from the browser.
 * -------------------------------------------------------------------------------------------------
 */
