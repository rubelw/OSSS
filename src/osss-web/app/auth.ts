import NextAuth, { type NextAuthConfig } from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

export const authConfig: NextAuthConfig = {
  session: { strategy: "jwt" },
  providers: [
    Keycloak({
      issuer: process.env.KEYCLOAK_ISSUER!,          // e.g. http://localhost:8085/realms/OSSS
      clientId: process.env.Web_KEYCLOAK_CLIENT_ID!,     // e.g. "osss-web"
      clientSecret: process.env.WEB_KEYCLOAK_CLIENT_SECRET || undefined, // omit/empty for Public client
      // Prevents “Missing parameter: code_challenge_method”
      checks: ["pkce", "state"],
      authorization: { params: { scope: "openid profile email" } },
    }),
  ],
  // Having a secret avoids server-side errors that render HTML
  secret: process.env.AUTH_SECRET,
  debug: process.env.NODE_ENV === "development",
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
