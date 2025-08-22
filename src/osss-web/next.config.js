/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      // proxy ONLY your backend paths, e.g. /api/osss/**
      {
        source: "/api/osss/:path*",
        destination: "http://localhost:8081/:path*",
      },
      // do NOT add a catch-all /api/:path* rewrite
    ];
  },
};

const path = require('path');

module.exports = {
  outputFileTracingRoot: path.join(__dirname, '../../'),
};