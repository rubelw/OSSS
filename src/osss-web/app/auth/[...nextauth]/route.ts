// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

export const authOptions = {
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,        // e.g. "osss-web"
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!, // from Keycloak client credentials
      issuer: process.env.KEYCLOAK_ISSUER!,              // e.g. "http://localhost:8085/realms/OSSS"
    }),
  ],
  // (optional) customize session/jwt/callbacks here
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };

