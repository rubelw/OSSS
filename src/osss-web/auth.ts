// src/osss-web/auth.ts
import { getServerSession, type NextAuthOptions } from "next-auth";
import KeycloakProvider from "next-auth/providers/keycloak";

export const authOptions: NextAuthOptions = {
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,       // e.g. "osss-web"
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
      issuer: process.env.KEYCLOAK_ISSUER!,            // e.g. "http://localhost:8085/realms/OSSS"
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      if (account?.access_token) token.accessToken = account.access_token;
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken as string | undefined;
      return session;
    },
  },
};

// v4-friendly helper so you can do `const session = await auth()`
export const auth = () => getServerSession(authOptions);
export default authOptions;
