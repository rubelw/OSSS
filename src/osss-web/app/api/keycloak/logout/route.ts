import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
// Optional: decode azp from id_token to verify client
// import { decodeJwt } from "jose";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const jwt = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  const issuer = process.env.KEYCLOAK_ISSUER!;
  const envClient = process.env.WEB_KEYCLOAK_CLIENT_ID || "osss-web";
  const postRaw =
    process.env.POST_LOGOUT_REDIRECT_URI ?? `${req.nextUrl.origin}/`;
  const post = postRaw.endsWith("/") ? postRaw : `${postRaw}/`;

  // const azp = jwt?.id_token ? (decodeJwt(jwt.id_token).azp as string | undefined) : undefined;

  const url = new URL(`${issuer}/protocol/openid-connect/logout`);
  if (jwt?.id_token) url.searchParams.set("id_token_hint", String(jwt.id_token));

  // Only include client_id if it's the WEB client; otherwise omit to avoid mismatches
  if (envClient === "osss-web") {
    url.searchParams.set("client_id", envClient);
  }

  url.searchParams.set("post_logout_redirect_uri", post);

  // Optional: debug mode ?inspect=1 shows what the route is using
  if (req.nextUrl.searchParams.get("inspect") === "1") {
    const body = {
      issuer,
      usingClientId: envClient === "osss-web" ? envClient : "(omitted)",
      hasIdToken: Boolean(jwt?.id_token),
      // azpFromIdToken: azp,
      post_logout_redirect_uri: post,
      finalLogoutUrl: url.toString(),
    };
    return NextResponse.json(body);
  }

  return NextResponse.redirect(url.toString());
}
