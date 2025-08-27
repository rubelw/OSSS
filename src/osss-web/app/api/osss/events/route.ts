import { auth } from "@/lib/auth";
import { env } from "@/lib/env";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export async function GET(_req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;   // 👈 await the Promise
  const session = await auth();
  const accessToken = (session as any)?.accessToken;
  if (!accessToken) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const base = env.OSSS_API_URL?.replace(/\/+$/, "");
  const url = `${base}/activities/events`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` }, cache: "no-store" });
  const text = await r.text();
  if (!r.ok) return NextResponse.json({ error: "upstream_error", status: r.status, details: text }, { status: r.status });
  return NextResponse.json(JSON.parse(text));
}
