// app/api/a2a/runs/[id]/route.ts
import { NextResponse } from "next/server";
import { a2aFetch } from "../../_client";

interface Params {
  params: { id: string };
}

export async function GET(_: Request, { params }: Params) {
  const { id } = params;
  try {
    const data = await a2aFetch(`/admin/runs/${encodeURIComponent(id)}`);
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { error: String(e?.message || e) },
      { status: 500 }
    );
  }
}
