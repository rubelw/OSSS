// src/osss-web/app/api/debug/session/route.ts
import { NextResponse } from "next/server";
import { auth } from "@/app/auth"; // ✅ use central NextAuth export

export async function GET() {
  const session = await auth();
  return NextResponse.json({
    signedIn: !!session,
    hasAccessToken: Boolean((session as any)?.accessToken),
  });
}
