import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { apiGet } from "@/lib/api-client";

export async function GET() {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;

  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const data = await apiGet("/schools", accessToken);
  return NextResponse.json(data);
}
