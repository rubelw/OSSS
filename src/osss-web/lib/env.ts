/**
 * =================================================================================================
 * OSSS Web — Environment Utilities
 * -------------------------------------------------------------------------------------------------
 * Purpose: Centralize reading & validating environment variables.
 *  Validates presence/format; throws clear errors at boot to fail fast.
 *  Separates server-only secrets (never exposed to client) from public variables prefixed with NEXT_PUBLIC_.
 *
 * General guidance
 *  • This module is server-only unless otherwise stated; do not import into client components.
 *  • Prefer explicit, validated environment access (no silent fallbacks).
 *  • Keep exported surface minimal and stable; this module is a building block for the app.
 * =================================================================================================
 */
// lib/env.ts
import { z } from "zod";

const Env = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),

  // AuthJS / Keycloak
  AUTH_SECRET: z.string().min(1),
  AUTH_TRUST_HOST: z.string().optional(),

  KEYCLOAK_ISSUER: z.string().url().optional(),
  NEXT_PUBLIC_KEYCLOAK_BASE: z.string().url().optional(),
  NEXT_PUBLIC_KEYCLOAK_REALM: z.string().optional(),

  WEB_KEYCLOAK_CLIENT_ID: z.string().default("osss-web"),
  WEB_KEYCLOAK_CLIENT_SECRET: z.string().optional(),

  // >>> Add this <<<
  OSSS_API_URL: z.string().url().default("http://127.0.0.1:8081"),
});

/**
 * Validated environment map `env`
 *  Contains only the variables this app relies on.
 *  Values are validated at import time; missing/invalid values throw with a helpful message.
 *  Separate maps for `server` and `public` are recommended when using Next.js.
 */
export const env = Env.parse(process.env);

/**
 * -------------------------------------------------------------------------------------------------
 * Operational notes
 *  • Observability: log request ids and lightweight outcome metrics; never log raw tokens.
 *  • Security: ensure all outbound calls to Keycloak/backends use HTTPS and strict TLS.
 *  • Resilience: handle transient failures with jittered backoff; fail fast on configuration errors.
 *  • Testing: mock network calls (fetch) and time (Date.now) for deterministic token/expiry tests.
 * -------------------------------------------------------------------------------------------------
 */
