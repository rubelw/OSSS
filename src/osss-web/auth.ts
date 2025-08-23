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

export const { handlers, auth, signIn, signOut } = NextAuth({
  debug: process.env.AUTH_DEBUG === "1",
  secret: must(process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET, "AUTH_SECRET"),
  session: { strategy: "jwt" },
  // trust localhost in dev; require explicit trust or AUTH_URL in prod
  trustHost: process.env.AUTH_TRUST_HOST === "1" || process.env.NODE_ENV !== "production",
  providers: [
    Keycloak({
      issuer,
      clientId,
      ...(clientSecret ? { clientSecret } : {}),
      authorization: { params: { scope: "openid profile email" } },
    }),
  ],
  callbacks: {
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
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      (session as any).idToken = token.idToken;
      (session as any).error = (token as any).error;
      return session;
    },
  },
});
