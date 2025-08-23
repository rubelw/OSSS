// src/osss-web/app/api/osss/schools/route.ts
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import { auth } from "@/auth";

export async function GET() {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;

  if (!accessToken) {
    // Not signed in or token not present in session
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const data = await apiGet("/schools", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message ?? "Upstream error" }, { status: 502 });
  }
}
