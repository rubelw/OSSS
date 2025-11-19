// app/api/a2a/runs/route.ts
import { NextRequest, NextResponse } from "next/server";
import { a2aFetch } from "../_client";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const limit = searchParams.get("limit") ?? "50";

  try {
    const data = await a2aFetch(`/admin/runs?limit=${encodeURIComponent(limit)}`);
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { error: String(e?.message || e) },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  try {
    const data = await a2aFetch("/admin/runs", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { error: String(e?.message || e) },
      { status: 500 }
    );
  }
}
