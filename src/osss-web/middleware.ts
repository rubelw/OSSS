// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export const config = {
  matcher: ["/((?!api/auth|_next|static|favicon.ico|assets).*)"],
};

export function middleware(_req: NextRequest) {
  // No auth() here when using DB sessions. Do only cheap checks if needed.
  return NextResponse.next();
}
