// app/api/auth/[...nextauth]/route.ts
export const runtime = 'nodejs';

import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

// Optional Redis adapter (only used if env is present)
import { RedisAdapter } from "@auth/redis-adapter";
import Redis from "ioredis";

function buildRedis() {
  // Prefer a single REDIS_URL, else fall back to host/port/db envs.
  const url = process.env.REDIS_URL;
  if (url && url.trim()) {
    return new Redis(url, {
      maxRetriesPerRequest: 2,
      enableAutoPipelining: true,
    });
  }

  // Fallback to discrete env vars, defaulting to the compose service name "redis"
  const host = process.env.REDIS_HOST ?? "redis";
  const port = Number(process.env.REDIS_PORT ?? "6379");
  const db = Number(process.env.REDIS_DB ?? "0");

  // If user explicitly set REDIS_HOST/PORT/DB or we detect the default "redis",
  // initialize the client. If you want to *only* use Redis when envs are set,
  // add a guard to return null when REDIS_HOST is unset.
  return new Redis({ host, port, db, maxRetriesPerRequest: 2, enableAutoPipelining: true });
}

const maybeRedis = (() => {
  // Enable Redis adapter only when clearly configured.
  // If you’d rather *always* try Redis, remove this guard.
  if (
    (process.env.REDIS_URL && process.env.REDIS_URL.trim()) ||
    process.env.REDIS_HOST || process.env.REDIS_PORT || process.env.REDIS_DB
  ) {
    return buildRedis();
  }
  return null;
})();

const auth = NextAuth({
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,        // e.g. "osss-web"
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,// from Keycloak client credentials
      issuer: process.env.KEYCLOAK_ISSUER!,             // e.g. "https://keycloak:8443/realms/OSSS"
    }),
  ],

  // If Redis is configured, use it; otherwise fall back to JWT sessions.
  ...(maybeRedis
    ? { adapter: RedisAdapter(maybeRedis) }
    : { /* no adapter => JWT sessions by default */ }),

  // Required in dev behind proxies / different hosts
  trustHost: true,

  // Use whichever you’ve set; either is fine with Auth.js v5
  secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,

  // Helpful logs during setup
  logger: {
    error(code, meta) { console.error("[auth][error]", code, meta); },
    warn(code) { console.warn("[auth][warn]", code); },
    debug(code, meta) { console.log("[auth][debug]", code, meta); },
  },
});

// Export route handlers
export const { handlers: { GET, POST } } = auth;
