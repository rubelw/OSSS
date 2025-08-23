// src/osss-web/app/api/osss/states/route.ts
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import { auth } from "@/auth";

export async function GET() {
  try {
    const session = await auth();
    const accessToken = (session as any)?.accessToken as string | undefined;

    if (!accessToken) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const data = await apiGet("/states", accessToken);
    return NextResponse.json(data ?? []);
  } catch (err: any) {
    // If the upstream rejected the token, return 401 to the browser (not 500)
    const msg = String(err?.message || "");
    if (msg.startsWith("API 401")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    console.error("[states route] error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
