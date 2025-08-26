// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

async function refreshKeycloakAccessToken(token: any) {
  try {
    const url = `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`;
    const body = new URLSearchParams({
      client_id: process.env.WEB_KEYCLOAK_CLIENT_ID!,
      client_secret: process.env.WEB_KEYCLOAK_CLIENT_SECRET ?? "", // if public client, leave blank + remove from Keycloak
      grant_type: "refresh_token",
      refresh_token: token.refresh_token as string,
    });

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });

    if (!res.ok) throw new Error("Failed to refresh token");

    const data = await res.json();

    return {
      ...token,
      access_token: data.access_token,
      refresh_token: data.refresh_token ?? token.refresh_token,
      expires_at: Math.floor(Date.now() / 1000) + (data.expires_in ?? 300) - 10,
      id_token: data.id_token ?? token.id_token,
      error: null,
    };
  } catch {
    return { ...token, error: "RefreshAccessTokenError" as const };
  }
}

export const {
  handlers: { GET, POST },
  auth,
  signIn,
  signOut,
} = NextAuth({
  secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
  providers: [
    Keycloak({
      issuer: process.env.KEYCLOAK_ISSUER,      // e.g. http://localhost:8085/realms/OSSS
      clientId: process.env.WEB_KEYCLOAK_CLIENT_ID, // e.g. osss-web
      clientSecret: process.env.WEB_KEYCLOAK_CLIENT_SECRET, // omit if public
      authorization: { params: { scope: "openid profile email" } }, // keep minimal
      client: { token_endpoint_auth_method: process.env.WEB_KEYCLOAK_CLIENT_SECRET ? "client_secret_post" : "none" },
    }),
  ],
  session: {
    strategy: "jwt",
    // Do NOT increase cookie size limits; keep payload small instead.
  },
  callbacks: {
    async jwt({ token, account }) {
      // On initial sign-in
      if (account) {
        token.access_token = account.access_token;
        token.refresh_token = account.refresh_token;
        token.expires_at = Math.floor(Date.now() / 1000) + (account.expires_in ?? 300) - 10;
        token.id_token = account.id_token; // optional; useful for KC logout
        // IMPORTANT: don't copy decoded claims/roles into the token
      }

      // Refresh if expired (or close)
      if (token.expires_at && Date.now() / 1000 >= token.expires_at) {
        return await refreshKeycloakAccessToken(token);
      }

      return token;
    },

    async session({ session, token }) {
      // Keep the session tiny. Just expose booleans and small flags.
      (session as any).hasAccessToken = Boolean(token.access_token);
      (session as any).tokenError = token.error ?? null;
      // Do NOT attach roles/claims to session — fetch them on demand server-side if needed.
      return session;
    },
  },
});
