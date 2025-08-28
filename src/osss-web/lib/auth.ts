/**
 * =================================================================================================
 * OSSS Web – Authentication Bootstrap (Auth.js/NextAuth + Keycloak + Redis via unstorage)
 * -------------------------------------------------------------------------------------------------
 * This module wires up:
 *   • Environment + runtime configuration (Next.js server env)
 *   • Redis-backed unstorage adapter for user/account persistence in Node runtimes
 *   • Keycloak OAuth/OIDC provider with a trimmed `profile` mapper
 *   • Auth.js (NextAuth) initialization exporting:
 *       - `auth`  : middleware-style helper to protect routes (v5)
 *       - `signIn`/`signOut` helpers
 *       - `GET`/`POST` route handlers for /api/auth/[...nextauth]
 *
 * Why Redis via unstorage?
 *   - Works in Node runtimes (not Edge) and is simpler than a full SQL adapter while developing.
 *   - Sessions are JWT-based so requests on Edge don’t need Redis; user/account persistence remains
 *     available on the Node side for Auth.js flows.
 *
 * Operational notes:
 *   - This file MUST run only on the server (no client imports) because it reads secrets from
 *     process.env and initializes server-only connections.
 *   - Required env vars are documented below; missing or malformed values will surface as 500s on
 *     /api/auth/session or when the provider is called.
 *   - If Redis is password-protected, we build a Redis URL of the form: redis://:<PASS>@host:port
 *   - Avoid deep-importing .d.ts files from node_modules; use package entry points only.
 *
 * Troubleshooting quick hits:
 *   - “only valid absolute URLs can be requested” → KEYCLOAK_ISSUER and NEXTAUTH_URL must be absolute.
 *   - 500 with “providers.map is not a function” → don’t call NextAuth(config) until you pass a real
 *     config (ensure `providers: [...]` exists) and export handlers correctly.
 *   - ECONNREFUSED to Redis → container not running or wrong password. Validate with redis-cli -a.
 * =================================================================================================
 */
// lib/auth.ts
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";
import { UnstorageAdapter } from "@auth/unstorage-adapter";
import { createStorage } from "unstorage";
import redisDriver from "unstorage/drivers/redis";

/**
 * -----------------------------
 * Environment variable contract
 * -----------------------------
 * The following variables are consumed at module init time. They should be present in `.env.local`
 * for development, or in the host environment in production:
 *
 *   NEXTAUTH_URL                – Absolute URL for your app (e.g. http://localhost:3000)
 *   NEXTAUTH_SECRET             – Long random secret for JWT/session encryption
 *   KEYCLOAK_ISSUER            – Absolute realm issuer URL (e.g. https://kc.example.com/realms/OSSS)
 *   WEB_KEYCLOAK_CLIENT_ID     – Keycloak client id registered for this app
 *   WEB_KEYCLOAK_CLIENT_SECRET – Keycloak client secret for the above client
 *   REDIS_URL                  – Base Redis URL without credentials (e.g. redis://127.0.0.1:6379)
 *   REDIS_PASSWORD             – Optional password; when set we inject it into the final URL
 *   NODE_ENV                   – 'development' enables verbose Auth.js debug logging
 *
 * SECURITY: Never expose these values to the browser; this file runs server-side only.
 */
const {
  KEYCLOAK_ISSUER,
  WEB_KEYCLOAK_CLIENT_ID,
  WEB_KEYCLOAK_CLIENT_SECRET,
  NODE_ENV,
  REDIS_URL,
  REDIS_PASSWORD,
} = process.env;

/**
 * ------------------------------------------------------------------------------
 * Redis URL normalisation
 * ------------------------------------------------------------------------------
 * We accept either:
 *   • REDIS_URL alone (no auth):    redis://127.0.0.1:6379
 *   • REDIS_URL + REDIS_PASSWORD:   redis://:<password>@127.0.0.1:6379
 *
 * Why build `finalRedisUrl` this way?
 *   - Many Redis clients prefer credentials embedded in the URL.
 *   - We URL-encode the password to safely handle special characters.
 *   - `lazyConnect` defers opening the TCP connection until first use (faster boot).
 *   - `maxRetriesPerRequest` bounds re-tries to prevent hang during outages.
 */
const baseRedisUrl = REDIS_URL || "redis://127.0.0.1:6379";
const url = new URL(baseRedisUrl);
const finalRedisUrl =
  REDIS_PASSWORD && REDIS_PASSWORD.trim()
    ? `redis://:${encodeURIComponent(REDIS_PASSWORD)}@${url.host}${url.pathname || ""}`
    : baseRedisUrl;

/**
 * ------------------------------------------------------------------------------
 * unstorage + Redis driver
 * ------------------------------------------------------------------------------
 * `unstorage` is a pluggable KV abstraction used by the `@auth/unstorage-adapter`.
 * Here we create a storage instance backed by Redis for accounts/users/etc. (Node runtime).
 * NOTE: Sessions are JWT-based (`session.strategy = "jwt"`), so Edge requests do not need Redis.
 */
const storage = createStorage({
  driver: redisDriver({
    url: finalRedisUrl,
    maxRetriesPerRequest: 2,
    lazyConnect: true,
  }),
});

export const {
  auth,
  signIn,
  signOut,
  handlers: { GET, POST },
} = NextAuth(
  /**
   * ----------------------------------------------------------------------------
   * Auth.js (NextAuth) configuration
   * ----------------------------------------------------------------------------
   * - `debug`: extra logs in development (prints to server console)
   * - `trustHost`: allows Proxy/CDN/preview hosts to be treated as trusted (important in dev)
   * - `adapter`: UnstorageAdapter(storage) persists users/accounts in Redis
   * - `session.strategy = "jwt"`: issues stateless JWT sessions; reduces server lookups per request
   * - `providers`: Keycloak configured with PKCE and a trimmed profile mapper (smaller session payload)
   * - `callbacks.jwt`: shapes what’s persisted in the JWT; we keep it minimal and copy tokens on login
   * - `callbacks.session`: exposes `user.id` and `accessToken` to the client session object
   *
   * Exported API:
   *   { auth, signIn, signOut, handlers: { GET, POST } }
   *   - Re-export GET/POST from `app/api/auth/[...nextauth]/route.ts` to wire the auth routes.
   */
  {
    debug: NODE_ENV === "development",
    trustHost: true,

    // Users/accounts in Redis, sessions are JWT (no Redis on Edge)
    adapter: UnstorageAdapter(storage),
    session: { strategy: "jwt" },

    providers: [
      /**
       * Keycloak provider:
       * - `issuer` MUST be an absolute URL to your realm (/.well-known/openid-configuration must resolve)
       * - `checks: ["pkce"]` ensures confidential clients use PKCE for improved security
       * - `authorization.params.scope` requests standard OIDC claims (openid, profile, email)
       * - `profile(profile)` trims the default mapping to keep the user object lean
       */
      Keycloak({
        issuer: KEYCLOAK_ISSUER!,
        clientId: WEB_KEYCLOAK_CLIENT_ID!,
        clientSecret: WEB_KEYCLOAK_CLIENT_SECRET!,
        checks: ["pkce"],
        authorization: { params: { scope: "openid profile email" } },
        // make the "user" object small
        profile(profile) {
          return {
            id: profile.sub,
            name: profile.preferred_username ?? profile.name ?? null,
            email: profile.email ?? null,
          };
        },
      }),
    ],

    /**
     * JWT callback:
     * - First call (with `account`) happens right after successful OAuth sign-in.
     * - We copy access token & expiry from the provider into our JWT for later API calls (optional).
     * - On subsequent calls (no `account`), we preserve the minimal set of stable attributes.
     * NOTE: Keep the JWT small to avoid cookie bloat when using `session.strategy = "jwt"`.
     */
    callbacks: {
      async jwt({ token, account, user }) {
        // On initial sign-in, build a minimal token
        if (account) {
          return {
            sub: (user as any)?.id ?? token.sub, // keep a stable id
            name: user?.name ?? token.name ?? null,
            email: user?.email ?? token.email ?? null,
            accessToken: account.access_token as string | undefined,
            accessTokenExpires: account.expires_at as number | undefined,
          };
        }
        // Afterwards, keep it minimal (don’t accumulate extras)
        return {
          sub: token.sub,
          name: token.name ?? null,
          email: token.email ?? null,
          accessToken: (token as any).accessToken,
          accessTokenExpires: (token as any).accessTokenExpires,
        };
      },

      /**
       * Session callback:
       * - Shapes what’s sent to the client via `useSession()` and `/api/auth/session`.
       * - We attach `user.id` (from JWT `sub`) and bubble up `accessToken` when present.
       *   CAUTION: Do not include sensitive tokens you wouldn’t want exposed to the browser.
       */
      async session({ session, token }) {
        // expose id + access token on the session object
        (session.user as any).id = token.sub as string;
        (session as any).accessToken = (token as any).accessToken;
        return session;
      },
    },
  }
);
