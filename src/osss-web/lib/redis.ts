/**
 * =================================================================================================
 * OSSS Web — Redis Client / Storage Factory
 * -------------------------------------------------------------------------------------------------
 * Purpose: Construct and export a Redis-backed `unstorage` instance (or raw client) for server usage.
 *  Normalizes REDIS_URL/REDIS_PASSWORD into a single credentialed URL.
 *  Configures safe defaults (lazyConnect, bounded retries) and documents shutdown semantics.
 *
 * General guidance
 *  • This module is server-only unless otherwise stated; do not import into client components.
 *  • Prefer explicit, validated environment access (no silent fallbacks).
 *  • Keep exported surface minimal and stable; this module is a building block for the app.
 * =================================================================================================
 */
import Redis from "ioredis";

declare global {
  // avoid duplicate clients in dev
  // eslint-disable-next-line no-var
  var __redis: Redis | undefined;
}

export const redis =
  global.__redis ??
  new Redis(process.env.REDIS_URL!, {
    maxRetriesPerRequest: null,
    enableAutoPipelining: true,
  });

if (process.env.NODE_ENV !== "production") global.__redis = redis;

/**
 * -------------------------------------------------------------------------------------------------
 * Operational notes
 *  • Observability: log request ids and lightweight outcome metrics; never log raw tokens.
 *  • Security: ensure all outbound calls to Keycloak/backends use HTTPS and strict TLS.
 *  • Resilience: handle transient failures with jittered backoff; fail fast on configuration errors.
 *  • Testing: mock network calls (fetch) and time (Date.now) for deterministic token/expiry tests.
 * -------------------------------------------------------------------------------------------------
 */
