import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";

export async function GET() {
  try {
    const data = await apiGet("/states");
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 401 });
  }
}