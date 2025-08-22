// app/api/osss/states/route.ts

import { NextRequest, NextResponse } from "next/server";
import { headers as nextHeaders } from "next/headers";
import { auth } from "../../auth/[...nextauth]/route";

// Force Node runtime + no caching so logs always run at request time
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

const API_BASE =
  process.env.NEXT_PUBLIC_OSSS_API_BASE?.trim() || "http://127.0.0.1:8081";

function mask(str?: string, left = 6, right = 4) {
  if (!str) return "(none)";
  if (str.length <= left + right) return "(short)";
  return `${str.slice(0, left)}…${str.slice(-right)}`;
}

export async function GET(req: NextRequest) {
  // ---- request context & env
  const hdrs = nextHeaders();
  const method = req.method;
  const url = req.nextUrl?.toString?.() || "(unknown)";
  const cookieHeader = hdrs.get("cookie") || "";
  const cookieNames = req.cookies.getAll().map((c) => c.name);
  const hasNA =
    req.cookies.has("next-auth.session-token") ||
    req.cookies.has("__Secure-next-auth.session-token");
  const hasAuthJs =
    req.cookies.has("authjs.session-token") ||
    req.cookies.has("__Secure-authjs.session-token");

  console.log("[states] ===== request =====");
  console.log("[states] method:", method, "| url:", url);
  console.log("[states] API_BASE:", API_BASE);
  console.log("[states] cookie header len:", cookieHeader.length);
  console.log("[states] cookie names:", cookieNames);
  console.log("[states] has NextAuth cookie?", hasNA, "| has Auth.js cookie?", hasAuthJs);
  console.log("[states] env:", {
    NODE_ENV: process.env.NODE_ENV,
    NEXTAUTH_URL: process.env.NEXTAUTH_URL,
    NEXT_PUBLIC_KEYCLOAK_BASE: process.env.NEXT_PUBLIC_KEYCLOAK_BASE,
    NEXT_PUBLIC_KEYCLOAK_REALM: process.env.NEXT_PUBLIC_KEYCLOAK_REALM,
    NEXT_PUBLIC_KEYCLOAK_CLIENT_ID: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID,
    NEXT_PUBLIC_OSSS_API_BASE: process.env.NEXT_PUBLIC_OSSS_API_BASE,
  });

  // ---- session / token
  let session: any = null;
  try {
    session = await auth();
  } catch (e: any) {
    console.error("[states] auth() threw:", e?.message || e);
  }
  const sessionKeys = session ? Object.keys(session) : [];
  const accessToken: string | undefined = session?.accessToken;
  const expires = session?.expires ?? session?.expiresAt;

  console.log("[states] session present?", !!session, "| keys:", sessionKeys);
  console.log("[states] accessToken present?", !!accessToken, "| token:", mask(accessToken));
  if (expires) console.log("[states] session expiry:", expires);

  if (!accessToken) {
    const debug = {
      cookieNames,
      hasNextAuthCookie: hasNA,
      hasAuthJsCookie: hasAuthJs,
      sessionKeys,
      apiBase: API_BASE,
    };
    console.warn("[states] No access token in session — returning 401", debug);
    return NextResponse.json(
      {
        error: "No session access token. Sign in first.",
        debug,
      },
      { status: 401, headers: { "x-debug": JSON.stringify(debug) } }
    );
  }

  // ---- call FastAPI with Bearer
  const target = `${API_BASE}/states`;
  console.log("[states] → FastAPI:", target);

  try {
    const res = await fetch(target, {
      method: "GET",
      headers: {
        accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
    });

    console.log("[states] FastAPI status:", res.status);
    const text = await res.text();

    return new NextResponse(text, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (err: any) {
    console.error("[states] Fetch to FastAPI failed:", err?.message || err);
    return NextResponse.json(
      { error: "Failed to contact API", detail: String(err?.message || err) },
      { status: 502 }
    );
  }
}
