// app/api/osss/[...path]/route.ts
import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.OSSS_API_URL ?? "http://localhost:8000";

function targetURL(segments: string[], search: string) {
  const path = segments.join("/");
  return `${BASE}/${path}${search ? `?${search}` : ""}`;
}

async function proxy(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> } // <-- params is a Promise in Next 15
) {
  const { path = [] } = await ctx.params;       // <-- await it
  const url = targetURL(path, req.nextUrl.searchParams.toString());

  // Pass through body for non-GET/HEAD
  const body =
    req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer();

  // Strip hop-by-hop headers that can confuse the upstream
  const headers = new Headers(req.headers);
  ["host", "connection", "content-length", "accept-encoding"].forEach((h) =>
    headers.delete(h)
  );

  const res = await fetch(url, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  });

  // Stream response back, preserving headers/status
  const outHeaders = new Headers(res.headers);
  return new NextResponse(res.body, {
    status: res.status,
    headers: outHeaders,
  });
}

// Export handlers
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;

