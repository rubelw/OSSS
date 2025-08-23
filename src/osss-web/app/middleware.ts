import { auth } from "./auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { nextUrl } = req;
  const isAuthed = !!req.auth; // session or null
  const protectedPrefixes = ["/states", "/schools", "/dashboard", "/account", "/protected"];

  if (protectedPrefixes.some((p) => nextUrl.pathname.startsWith(p)) && !isAuthed) {
    const cb = nextUrl.pathname + nextUrl.search;
    const url = new URL("/api/auth/signin", nextUrl.origin);
    url.searchParams.set("callbackUrl", cb);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/states", "/schools", "/dashboard/:path*", "/account/:path*", "/protected/:path*", "/api/osss/:path*"],
};
