// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

const isConfidential = !!process.env.KEYCLOAK_CLIENT_SECRET;

async function refreshKeycloakAccessToken(token: any) {
  try {
    const url = `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`;
    const body = new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: token.refreshToken as string,
      client_id: process.env.WEB_KEYCLOAK_CLIENT_ID as string,
    });
    if (process.env.KEYCLOAK_CLIENT_SECRET) {
      body.set("client_secret", process.env.WEB_KEYCLOAK_CLIENT_SECRET);
    }

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const data = await res.json();
    if (!res.ok) throw data;

    return {
      ...token,
      accessToken: data.access_token,
      idToken: data.id_token ?? token.idToken,
      refreshToken: data.refresh_token ?? token.refreshToken,
      // seconds from now
      expiresAt: Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600),
      error: undefined,
    };
  } catch (e) {
    console.error("refreshKeycloakAccessToken error", e);
    return { ...token, error: "RefreshAccessTokenError" as const };
  }
}

export const {
  handlers: { GET, POST },
  auth,
  signIn,
  signOut,
} = NextAuth({
  providers: [
    Keycloak({
      issuer: process.env.KEYCLOAK_ISSUER,          // http://localhost:8085/realms/OSSS
      clientId: process.env.WEB_KEYCLOAK_CLIENT_ID,     // osss-web
      ...(isConfidential
        ? { clientSecret: process.env.WEB_KEYCLOAK_CLIENT_SECRET }      // confidential
        : { client: { token_endpoint_auth_method: "none" } }),      // public (PKCE)
      authorization: { params: { scope: "openid profile email" } },
    }),
  ],
  session: { strategy: "jwt" },

  callbacks: {
    async jwt({ token, account }) {
      // Initial sign-in: copy tokens from provider
      if (account) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.idToken = account.id_token;
        token.expiresAt =
          account.expires_at ??
          Math.floor(Date.now() / 1000) + (account.expires_in ?? 3600);
      }

      // Refresh if expiring/expired (with 60s buffer)
      if (token.expiresAt && Date.now() / 1000 > token.expiresAt - 60) {
        return await refreshKeycloakAccessToken(token);
      }
      return token;
    },

    async session({ session, token }) {
      // expose a boolean and (optionally) the token for your debug UI
      (session as any).hasAccessToken = Boolean(token.accessToken);
      (session as any).accessToken = token.accessToken ?? null;
      (session as any).idToken = token.idToken ?? null;
      (session as any).tokenError = token.error ?? null;
      return session;
    },
  },

  // optional while debugging
  // debug: true,
});
