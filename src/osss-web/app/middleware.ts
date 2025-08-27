/**
 * OSSS Web — Next.js Middleware (Edge Runtime)
 * Purpose: Early request handling (auth gate, rewrites/redirects) before route handlers.
 * Runtime: Edge — only Web APIs; avoid Node modules, DB clients, or long CPU work.
 * Matcher: Configure `export const config.matcher` to limit which paths hit middleware.
 * Security: Never leak secrets; read only signed cookies or headers you control.
 */

export { auth as middleware } from "@/lib/auth";
