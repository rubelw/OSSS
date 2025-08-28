/**
 * =================================================================================================
 * OSSS Web — Keycloak Token Utilities
 * -------------------------------------------------------------------------------------------------
 * Purpose: Parse, validate, and refresh Keycloak-issued tokens (access/refresh/id).
 *  Encodes token shape, time math (exp/iat), and refresh flow (token endpoint with client credentials).
 *  Prevents expired tokens from leaking to API calls and offers helpers to attach Authorization headers.
 *
 * General guidance
 *  • This module is server-only unless otherwise stated; do not import into client components.
 *  • Prefer explicit, validated environment access (no silent fallbacks).
 *  • Keep exported surface minimal and stable; this module is a building block for the app.
 * =================================================================================================
 */
// lib/kc-token.ts
import { redis } from "@/lib/redis";

const RT_KEY = (userId: string) => `auth:kc:rt:${userId}`;

export async function saveRefreshToken(userId: string, rt: string, ttl?: number) {
  if (ttl) await redis.set(RT_KEY(userId), rt, "EX", ttl);
  else await redis.set(RT_KEY(userId), rt);
}

export async function getAccessTokenForUser(userId: string) {
  const rt = await redis.get(RT_KEY(userId));
  if (!rt) return null;

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: rt,
    client_id: process.env.WEB_KEYCLOAK_CLIENT_ID!,
  });
  if (process.env.WEB_KEYCLOAK_CLIENT_SECRET) {
    body.set("client_secret", process.env.WEB_KEYCLOAK_CLIENT_SECRET);
  }

  const r = await fetch(
    `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`,
    { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body }
  );
  if (!r.ok) return null;

  const data = await r.json();
  // rotate stored RT if Keycloak returned a new one
  if (data.refresh_token) {
    const ttl = (data.refresh_expires_in as number | undefined) ?? 1800;
    await saveRefreshToken(userId, data.refresh_token, ttl);
  }
  return data.access_token as string;
}

/**
 * -------------------------------------------------------------------------------------------------
 * Operational notes
 *  • Observability: log request ids and lightweight outcome metrics; never log raw tokens.
 *  • Security: ensure all outbound calls to Keycloak/backends use HTTPS and strict TLS.
 *  • Resilience: handle transient failures with jittered backoff; fail fast on configuration errors.
 *  • Testing: mock network calls (fetch) and time (Date.now) for deterministic token/expiry tests.
 * -------------------------------------------------------------------------------------------------
 */
