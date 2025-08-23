import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { env } from "@/lib/env";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;
  if (!accessToken) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const base = env.OSSS_API_URL?.replace(/\/+$/, "");
  const r = await fetch(`${base}/activities/events/${params.id}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  const text = await r.text();
  if (!r.ok) return NextResponse.json({ error: "upstream_error", status: r.status, details: text }, { status: r.status });
  return NextResponse.json(JSON.parse(text));
}
