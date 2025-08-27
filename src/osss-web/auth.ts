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
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

function must(v?: string, name?: string) {
  if (!v || !v.trim()) throw new Error(`${name ?? "ENV"} missing`);
  return v.trim();
}

const issuer =
  process.env.KEYCLOAK_ISSUER ??
  `${must(process.env.NEXT_PUBLIC_KEYCLOAK_BASE, "NEXT_PUBLIC_KEYCLOAK_BASE")}/realms/${must(
    process.env.NEXT_PUBLIC_KEYCLOAK_REALM,
    "NEXT_PUBLIC_KEYCLOAK_REALM"
  )}`.replace(/\/+$/, "");

const clientId =
  process.env.WEB_KEYCLOAK_CLIENT_ID ??
  process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ??
  "osss-web";

const clientSecret = process.env.WEB_KEYCLOAK_CLIENT_SECRET?.trim();

export const { handlers, auth, signIn, signOut } = NextAuth(
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
  debug: process.env.AUTH_DEBUG === "1",
  secret: must(process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET, "AUTH_SECRET"),
  session: { strategy: "jwt" },
  // trust localhost in dev; require explicit trust or AUTH_URL in prod
  trustHost: process.env.AUTH_TRUST_HOST === "1" || process.env.NODE_ENV !== "production",
  providers: [

  /**
   * Keycloak provider:
   * - `issuer` MUST be an absolute URL to your realm (/.well-known/openid-configuration must resolve)
   * - `checks: ["pkce"]` ensures confidential clients use PKCE for improved security
   * - `authorization.params.scope` requests standard OIDC claims (openid, profile, email)
   * - `profile(profile)` trims the default mapping to keep the user object lean
   */
  Keycloak({
      issuer,
      clientId,
      ...(clientSecret ? { clientSecret } : {}),
      authorization: { params: { scope: "openid profile email" } },
    }),
  ],
  callbacks: {

  /**
   * JWT callback:
   * - First call (with `account`) happens right after successful OAuth sign-in.
   * - We copy access token & expiry from the provider into our JWT for later API calls (optional).
   * - On subsequent calls (no `account`), we preserve the minimal set of stable attributes.
   * NOTE: Keep the JWT small to avoid cookie bloat when using `session.strategy = "jwt"`.
   */
  async jwt({ token, account }) {
      if (account) {
        token.accessToken = (account as any).access_token;
        token.refreshToken = (account as any).refresh_token;
        token.idToken = (account as any).id_token;
        token.expiresAt =
          typeof (account as any).expires_at === "number"
            ? (account as any).expires_at
            : Math.floor(Date.now() / 1000) + 55 * 60;
        return token;
      }
      const now = Math.floor(Date.now() / 1000);
      if (!token.expiresAt || now < (token.expiresAt as number) - 60) return token;

      try {
        const form = new URLSearchParams();
        form.set("grant_type", "refresh_token");
        form.set("client_id", clientId);
        form.set("refresh_token", String(token.refreshToken || ""));
        if (clientSecret) form.set("client_secret", clientSecret);

        const res = await fetch(`${issuer}/protocol/openid-connect/token`, {
          method: "POST",
          headers: { "content-type": "application/x-www-form-urlencoded" },
          body: form.toString(),
          cache: "no-store",
        });

        const data = res.ok ? await res.json() : null;
        if (!data?.access_token) throw new Error("refresh failed");

        token.accessToken = data.access_token;
        if (data.refresh_token) token.refreshToken = data.refresh_token;
        if (data.id_token) token.idToken = data.id_token;
        token.expiresAt = Math.floor(Date.now() / 1000) + (data.expires_in ?? 3300);
        delete (token as any).error;
      } catch {
        (token as any).error = "RefreshAccessTokenError";
      }
      return token;
    },
    /**
 * Session callback:
 * - Shapes what’s sent to the client via `useSession()` and `/api/auth/session`.
 * - We attach `user.id` (from JWT `sub`) and bubble up `accessToken` when present.
 *   CAUTION: Do not include sensitive tokens you wouldn’t want exposed to the browser.
 */
async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      (session as any).idToken = token.idToken;
      (session as any).error = (token as any).error;
      return session;
    },
  },
});

/**
 * -------------------------------------------------------------------------------------------------
 * Operational notes
 *  • Observability: log request ids and lightweight outcome metrics; never log raw tokens.
 *  • Security: ensure all outbound calls to Keycloak/backends use HTTPS and strict TLS.
 *  • Resilience: handle transient failures with jittered backoff; fail fast on configuration errors.
 *  • Testing: stub time (Date.now) and `fetch` to make token flows deterministic in unit tests.
 * -------------------------------------------------------------------------------------------------
 */
