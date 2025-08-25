// app/api/osss/states/route.ts
import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { env } from "@/lib/env";

export async function GET() {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;
  if (!accessToken) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const base = env.OSSS_API_URL?.replace(/\/+$/, "");
  if (!base) {
    return NextResponse.json(
      { error: "missing_config", message: "OSSS_API_URL is not set" },
      { status: 500 }
    );
  }

  const url = `${base}/api/states`;

  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
      },
      cache: "no-store",
    });

    const text = await res.text();
    const ct = res.headers.get("content-type") || "";

    if (!res.ok) {
      console.error("Upstream /states error", res.status, text);
      return NextResponse.json(
        { error: "upstream_error", status: res.status, details: text.slice(0, 400) },
        { status: res.status }
      );
    }

    return ct.includes("application/json")
      ? NextResponse.json(JSON.parse(text))
      : new NextResponse(text, { status: 200, headers: { "content-type": ct || "application/json" } });
  } catch (err: any) {
    console.error("Fetch to OSSS API failed", err);
    return NextResponse.json(
      { error: "bad_gateway", message: String(err?.message ?? err) },
      { status: 502 }
    );
  }
}
