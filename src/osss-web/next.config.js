// =================================================================================================
// OSSS Web — Next.js Configuration (next.config.js)
// -------------------------------------------------------------------------------------------------
// What this file controls
// • Build and runtime behavior for your Next.js app (both dev and production builds).
// • Custom URL rewrites (proxying the FastAPI backend during local development).
// • Serverless output file tracing root (monorepo-aware bundling).
//
// Important context for this repo
// • You appear to have a monorepo layout; `outputFileTracingRoot` is pointed two levels up so that
//   Next can locate dependencies outside of `src/osss-web` when bundling server code.
// • The `rewrites()` config proxies ONLY the backend API routes you explicitly list, which is safer
//   than a catch‑all `/api/:path*` (that would collide with Next’s own API routes).
//
/* Operational tips
 * 1) Environment parity:
 *    - Keep this file minimal and environment‑agnostic. Use env vars to flip behavior when needed.
 * 2) Rewrites vs Redirects:
 *    - Rewrites keep the URL bar unchanged while fetching from a different origin/path.
 *    - Redirects change the client URL (3xx) and trigger a new request from the browser.
 * 3) Security & CORS:
 *    - Rewrites happen at the Next.js server/proxy layer; your backend still needs proper CORS if
 *      it will be accessed directly by the browser in production (different origin).
 * 4) Monorepo pitfalls:
 *    - If you import code from the workspace root, make sure `outputFileTracingRoot` points high
 *      enough; otherwise the server bundle might miss required files at deploy time.
 * 5) Cache busting & images:
 *    - Configure `images.domains` / `images.remotePatterns` here if you load remote images.
 *    - Avoid over‑configuring here; prefer runtime/env‑driven behavior inside the app code.
 */
// =================================================================================================
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      // --- Rewrites block ---------------------------------------------------------------------------
// Purpose:
// • During local development, you likely run FastAPI on http://localhost:8081 (or similar).
// • Client code can call relative paths like `/api/osss/...` and Next will transparently
//   proxy the request to the backend, avoiding CORS headaches and not leaking backend hosts.
//
// Production considerations:
// • In production, you might serve the frontend and backend under different origins; in that
//   case, either remove the rewrite and call the absolute backend URL from the client (with
//   CORS allowed on the backend), or keep a reverse proxy in front (e.g., nginx, ingress).
//
// Safety notes:
// • Do NOT add a catch‑all `/api/:path*` rewrite; it would swallow Next’s own API routes and
//   potentially route sensitive paths to your backend unintentionally.
// proxy ONLY your backend paths, e.g. /api/osss/**
      {
  // Only proxy requests under /api/osss/** to your FastAPI service
  // Example: GET /api/osss/behaviorcodes  →  http://localhost:8081/behaviorcodes
  //          POST /api/osss/admin/users   →  http://localhost:8081/admin/users
  source: \"/api/osss/:path*\",
  destination: \"http://localhost:8081/:path*\",
},

      // do NOT add a catch-all /api/:path* rewrite — it would capture Next's own API routes and
      // break built-in endpoints like /api/auth or any /app/api/** handlers.
    ];
  }
};

const path = require('path');

// -------------------------------------------------------------------------------------------------
// Monorepo output tracing
// • Tells Next.js where the project root truly lives for the purpose of collecting server runtime
//   dependencies during build (a.k.a. "output file tracing").
// • If your app imports code from the monorepo root or sibling packages, this ensures those files
//   are copied to the standalone output (for serverless / Docker deploys).
// • Adjust the path join as needed if you move this app deeper or shallower in the repo tree.
// -------------------------------------------------------------------------------------------------
module.exports = {
  outputFileTracingRoot: path.join(__dirname, '../../'),
};


// -------------------------------------------------------------------------------------------------
// ⚠️ Note on exports
// • You define a `nextConfig` constant above, but it is not exported. If you intend to enable
//   those rewrites, you have two options:
//   1) Export everything in a single object including `rewrites` and `outputFileTracingRoot`, e.g.:
//
//      const path = require('path');
//      /** @type {import('next').NextConfig} */
//      const nextConfig = {
//        async rewrites() {
//          return [
//            {
//              source: "/api/osss/:path*",
//              destination: "http://localhost:8081/:path*",
//            },
//          ];
//        },
//        outputFileTracingRoot: path.join(__dirname, '../../'),
//      };
//      module.exports = nextConfig;
//
//   2) Or merge your current two blocks by spreading:
//      module.exports = { ...nextConfig, outputFileTracingRoot: path.join(__dirname, '../../') };
//
// • If you intentionally disabled the rewrites, you can leave it as-is, but keep in mind the proxy
//   won’t be active in dev.
// -------------------------------------------------------------------------------------------------
