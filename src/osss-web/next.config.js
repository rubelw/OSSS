// =================================================================================================
// OSSS Web — Next.js Configuration (next.config.js)
// -------------------------------------------------------------------------------------------------
// What this file controls
// • Build and runtime behavior for your Next.js app (both dev and production builds).
// • Custom URL rewrites (proxying the FastAPI backend during local development).
// • Serverless output file tracing root (monorepo-aware bundling).
// =================================================================================================

const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      // --- Rewrites block ---------------------------------------------------------------------------
      // Purpose:
      // • During local development, FastAPI runs inside Docker as the `app` service on port 8000.
      // • Client code can call relative paths like `/api/osss/...`, `/rag-images/...`, `/rag-pdfs/...`
      //   and Next will transparently proxy the request to the backend, avoiding CORS headaches.

      {
        // Only proxy requests under /api/osss/** to your FastAPI service
        // Example: GET /api/osss/behaviorcodes  →  http://app:8000/behaviorcodes
        //          POST /api/osss/admin/users   →  http://app:8000/admin/users
        source: '/api/osss/:path*',
        destination: 'http://app:8000/:path*',
      },

      {
        // Proxy image requests to FastAPI's static /rag-images mount
        // Example: GET /rag-images/main/foo.jpeg → http://app:8000/rag-images/main/foo.jpeg
        source: '/rag-images/:path*',
        destination: 'http://app:8000/rag-images/:path*',
      },

      {
        // NEW: proxy PDF links (used by RAG "Retrieved context") to FastAPI
        // Example: GET /rag-pdfs/main/DCG_BRAND_MANUAL.pdf → http://app:8000/rag-pdfs/main/DCG_BRAND_MANUAL.pdf
        source: '/rag-pdfs/:path*',
        destination: 'http://app:8000/rag-pdfs/:path*',
      },

      // do NOT add a catch-all /api/:path* rewrite — it would capture Next's own API routes and
      // break built-in endpoints like /api/auth or any /app/api/** handlers.
    ];
  },

  // Monorepo output tracing
  outputFileTracingRoot: path.join(__dirname, '../../'),
};

module.exports = nextConfig;
