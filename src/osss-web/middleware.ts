// middleware.ts — NextAuth v5 style
import { NextResponse } from "next/server";
import { auth } from "@/auth";

// Protect only these page paths with middleware.
// (Let your API routes check auth inside the route handler instead.)
const PROTECTED_PREFIXES = ["/states", "/schools"];

export default auth((req) => {
  const { pathname } = req.nextUrl;

  const needsAuth = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p));
  if (!needsAuth) return NextResponse.next();

  if (!req.auth) {
    const url = req.nextUrl.clone();
    url.pathname = "/api/auth/signin";
    url.searchParams.set("callbackUrl", req.nextUrl.href);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
});

// Don't run on /api or Next internals (prevents OpenID client issues on Edge)
export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
