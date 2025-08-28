/**
 * =================================================================================================
 * OSSS Web — Auth (Edge runtime adapter)
 * -------------------------------------------------------------------------------------------------
 * Purpose: Provide minimal Auth.js helpers safe for the Edge runtime.
 *  Edge constraints: no Node APIs, no TCP sockets, no Redis/ioredis; only Web APIs.
 *  Typical usage: route/middleware protection (`auth()`), token extraction from cookies/headers,
 *  and forwarding identity to backend requests as a short-lived bearer or opaque header.
 *
 * General guidance
 *  • This module is server-only unless otherwise stated; do not import into client components.
 *  • Prefer explicit, validated environment access (no silent fallbacks).
 *  • Keep exported surface minimal and stable; this module is a building block for the app.
 * =================================================================================================
 */
// src/osss-web/lib/auth-edge.ts
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

export const { auth } = NextAuth({
  // Edge-safe: no adapter here
  session: { strategy: "jwt" }, // fine for middleware-only checks
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
      issuer: process.env.KEYCLOAK_ISSUER!,
      checks: ["pkce"],
    }),
  ],
  // Keep callbacks minimal; middleware only needs `req.auth`
});

/**
 * -------------------------------------------------------------------------------------------------
 * Operational notes
 *  • Observability: log request ids and lightweight outcome metrics; never log raw tokens.
 *  • Security: ensure all outbound calls to Keycloak/backends use HTTPS and strict TLS.
 *  • Resilience: handle transient failures with jittered backoff; fail fast on configuration errors.
 *  • Testing: mock network calls (fetch) and time (Date.now) for deterministic token/expiry tests.
 * -------------------------------------------------------------------------------------------------
 */
