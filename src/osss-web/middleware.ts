// middleware.ts
export { default } from "next-auth/middleware";

export const config = {
  // protect pages and API routes that require auth
  matcher: ["/states", "/schools", "/api/osss/:path*"],
};
