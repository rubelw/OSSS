// app/api/a2a/health/route.ts
import { NextResponse } from "next/server";
import { a2aFetch } from "../_client";

export async function GET() {
  try {
    const data = await a2aFetch("/admin/health");
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { ok: false, error: String(e?.message || e) },
      { status: 500 }
    );
  }
}
