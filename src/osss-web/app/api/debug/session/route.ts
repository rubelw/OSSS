// app/api/debug/session/route.ts
import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "../../auth/[...nextauth]/route";

export async function GET() {
  const session = await getServerSession(authOptions);
  return NextResponse.json({
    signedIn: !!session,
    hasAccessToken: !!(session as any)?.accessToken,
  });
}