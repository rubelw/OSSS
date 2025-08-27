// src/osss-web/app/pages/api/keycloak/logout.ts
import type { NextApiRequest, NextApiResponse } from "next";
import { getToken } from "@auth/core/jwt";

/**
 * Pages Router API route that logs out Keycloak by clearing the session cookie/token.
 * Auth.js v5 `getToken` expects a Fetch Request or an object with headers. We map
 * NextApiRequest headers into a Headers object to satisfy types and runtime behavior.
 */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // Normalize Node headers -> Fetch Headers
    const headers = new Headers();
    for (const [key, val] of Object.entries(req.headers)) {
      if (typeof val === "string") headers.set(key, val);
      else if (Array.isArray(val)) headers.set(key, val.join(","));
      // ignore undefined
    }

    // Use the object form accepted by @auth/core/jwt
    const jwt = await getToken({
      req: { headers }, // ✅ type-safe for Auth.js v5
      secret: process.env.NEXTAUTH_SECRET!,
    });

    // Clear your session state (cookie names depend on your NextAuth/Auth.js setup)
    // Example: clearing NextAuth session cookie (adjust cookie names as needed)
    res.setHeader("Set-Cookie", [
      // Replace with your cookie names/domains/paths as appropriate:
      `next-auth.session-token=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
      `__Secure-next-auth.session-token=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
    ]);

    // If you also want to call KC end-session endpoint, do it here using jwt if needed:
    // const accessToken = (jwt as any)?.accessToken ?? (jwt as any)?.access_token;
    // await fetch(`${issuer}/protocol/openid-connect/logout`, {...})

    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("logout error:", err);
    return res.status(500).json({ ok: false, error: "logout_failed" });
  }
}
