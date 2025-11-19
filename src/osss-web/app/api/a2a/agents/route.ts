// app/api/a2a/agents/route.ts
import { NextResponse } from "next/server";
import { a2aFetch } from "../_client";

export async function GET() {
  try {
    const data = await a2aFetch("/admin/agents");
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { error: String(e?.message || e) },
      { status: 500 }
    );
  }
}
