// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import KeycloakProvider from "next-auth/providers/keycloak";

const handler = NextAuth({
  providers: [
    KeycloakProvider({
      issuer: process.env.KEYCLOAK_ISSUER,       // e.g. "http://localhost:8085/realms/OSSS"
      clientId: process.env.KEYCLOAK_CLIENT_ID!, // "osss-web"
      // For PUBLIC client, omit secret:
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET || undefined,
      authorization: { params: { scope: "openid profile email" } },
      // PKCE for public clients:
      checks: ["pkce", "state"],
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
        token.idToken = account.id_token;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      (session as any).idToken = token.idToken;
      return session;
    },
  },
});

export { handler as GET, handler as POST };
