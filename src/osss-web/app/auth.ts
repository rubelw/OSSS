/**
 * OSSS Web — Auth bootstrap (already commented elsewhere)
 * Note: A fully commented version exists; this header marks the top of this copy.
 */
// auth.ts (v5 style)
import NextAuth, { type NextAuthConfig } from "next-auth";
import Keycloak from "next-auth/providers/keycloak";
import { env } from "@/lib/env";

const issuer = `${env.NEXT_PUBLIC_KEYCLOAK_BASE.replace(/\/+$/, "")}/realms/${env.NEXT_PUBLIC_KEYCLOAK_REALM}`;

// 👇 Export the raw config object so Pages API routes can use getServerSession(req,res,authConfig)
export const authConfig: NextAuthConfig = {
  trustHost: env.AUTH_TRUST_HOST === "1",
  secret: env.AUTH_SECRET,
  session: { strategy: "jwt" },
  debug: env.AUTH_DEBUG === "1",
  providers: [
    Keycloak({
      issuer,
      clientId: env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID,
      clientSecret: env.WEB_KEYCLOAK_CLIENT_SECRET, // optional
      authorization: { params: { scope: "openid profile email" } },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = (account as any).access_token;
        token.refreshToken = (account as any).refresh_token ?? token.refreshToken;
        token.expiresAt =
          typeof (account as any).expires_at === "number"
            ? (account as any).expires_at
            : Math.floor(Date.now() / 1000) + 55 * 60;
        return token;
      }

      const now = Math.floor(Date.now() / 1000);
      if (!token.expiresAt || now < (token.expiresAt as number) - 60) return token;

      try {
        if (!token.refreshToken) return token;
        const form = new URLSearchParams();
        form.set("grant_type", "refresh_token");
        form.set("client_id", env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID);
        form.set("refresh_token", String(token.refreshToken));
        if (env.WEB_KEYCLOAK_CLIENT_SECRET) form.set("client_secret", env.WEB_KEYCLOAK_CLIENT_SECRET);

        const res = await fetch(`${issuer}/protocol/openid-connect/token`, {
          method: "POST",
          headers: { "content-type": "application/x-www-form-urlencoded" },
          body: form.toString(),
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`Refresh failed ${res.status}`);

        const data = await res.json();
        token.accessToken = data.access_token;
        if (data.refresh_token) token.refreshToken = data.refresh_token;
        token.expiresAt = Math.floor(Date.now() / 1000) + (data.expires_in ?? 3300);
        delete (token as any).error;
        return token;
      } catch {
        (token as any).error = "RefreshAccessTokenError";
        return token;
      }
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      return session;
    },
  },
};

// 👇 Export the NextAuth helpers for App Router usage
export const {
  handlers: { GET, POST },
  auth,
  signIn,
  signOut,
} = NextAuth(authConfig);

