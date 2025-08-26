import { NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

// tiny base64url -> JSON helper
function decodeJwtPayload(part: string) {
  let s = part.replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4;
  if (pad) s += "=".repeat(4 - pad);
  return JSON.parse(Buffer.from(s, "base64").toString("utf8"));
}

export async function GET(req: Request) {
  const secret = process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
  if (!secret) {
    return NextResponse.json(
      { error: "Server missing AUTH_SECRET/NEXTAUTH_SECRET" },
      { status: 500 }
    );
  }

  const token = await getToken({ req: req as any, secret });
  if (!token?.access_token) {
    return NextResponse.json({ error: "No access token" }, { status: 401 });
  }

  // Decode access token to read roles/claims
  let claims: any = {};
  try {
    const [, payload] = token.access_token.split(".");
    claims = decodeJwtPayload(payload);
  } catch {
    // ignore decode errors gracefully
  }

  const realmRoles = claims?.realm_access?.roles ?? [];
  const clientRoles = claims?.resource_access ?? {};
  const attributes = claims?.attributes ?? {};

  return NextResponse.json({ realmRoles, clientRoles, attributes, claims });
}
