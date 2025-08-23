// src/osss-web/middleware.ts
import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { nextUrl } = req;
  const isAuthed = !!req.auth;
  const protectedPrefixes = ["/states", "/schools", "/sis/behavior_codes", "/dashboard", "/account", "/protected"];

  if (protectedPrefixes.some((p) => nextUrl.pathname.startsWith(p)) && !isAuthed) {
    const url = new URL("/api/auth/signin", nextUrl.origin);
    url.searchParams.set("callbackUrl", nextUrl.pathname + nextUrl.search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/states/:path*", "/schools/:path*", "/behavior-codes/:path*", "/dashboard/:path*", "/account/:path*", "/protected/:path*", "/api/osss/:path*"],
};
