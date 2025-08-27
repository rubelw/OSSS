/**
 * =================================================================================================
 * OSSS Web — Next.js Middleware (Edge Runtime)
 * -------------------------------------------------------------------------------------------------
 * What this file does:
 *  • Runs on the **Edge** for every request that matches `config.matcher` (no Node APIs allowed).
 *  • Performs early checks & rewrites/redirects before reaching route handlers or pages.
 *  • Common duties: auth gate, locale negotiation, bot filtering, URL normalization, A/B routing.
 *
 * Edge runtime constraints:
 *  • No `process`, no TCP sockets, no file system, no Node polyfills. Only Web Platform APIs.
 *  • Use `Request`, `URL`, `Headers`, and Next's `NextRequest`/`NextResponse` helpers.
 *  • Keep logic fast and side‑effect free — this path runs very frequently.
 *
 * Observability:
 *  • Prefer small, structured headers (e.g., `x-osss-trace`, `x-geo`, `x-bot`) over console logs.
 *  • Avoid logging PII or secrets. Middleware executes in a highly shared environment.
 *
 * Performance:
 *  • Minimize regex and JSON work; parse the URL once; short‑circuit quickly when possible.
 *  • Rewrites keep the URL bar the same; redirects change the URL. Prefer rewrite when feasible.
 * =================================================================================================
 */
// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js matcher config
 *  • Controls which incoming requests invoke this middleware.
 *  • Use `matcher` to avoid expensive work on static assets (/_next/static, /_next/image, /favicon.ico).
 *  • Patterns support globs and segment parameters; test changes locally with a variety of URLs.
 *  • Example:
 *      matcher: ["/((?!_next/static|_next/image|favicon\.ico).*)"]
 */
export const config = {
  matcher: ["/((?!api/auth|_next|static|favicon.ico|assets).*)"],
};

/**
 * middleware(req): Next.js Edge entry point
 *  • Receives a NextRequest, returns NextResponse (or null to continue).
 *  • Typical flow:
 *      1) Parse the URL once: const { pathname, searchParams } = req.nextUrl
 *      2) Allowlist static assets and public routes to skip auth quickly
 *      3) Read auth state from cookies/headers (DO NOT use server-only helpers here)
 *      4) Redirect/Rewrite based on rules (auth, locale, maintenance, etc.)
 *      5) Fall back to /* Pass-through:
 *  - Call NextResponse.next() when no rules apply; downstream handlers will render the response.
 *  - You can still set small headers here (e.g., tracing) without impacting caching.
 */
export function middleware(_req: NextRequest) {
  // No auth() here when using DB sessions. Do only cheap checks if needed.
  return NextResponse.next();
}
