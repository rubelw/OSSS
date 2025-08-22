import { auth } from "./auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { nextUrl } = req;
  const isAuthed = !!req.auth;
  const protectedPrefixes = ["/dashboard", "/account", "/protected"];

  if (protectedPrefixes.some((p) => nextUrl.pathname.startsWith(p)) && !isAuthed) {
    const callbackUrl = nextUrl.pathname + nextUrl.search;
    const url = new URL("/api/auth/signin", nextUrl.origin);
    url.searchParams.set("callbackUrl", callbackUrl);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/dashboard/:path*", "/account/:path*", "/protected/:path*"],
};
