// app/api/osss/[...path]/route.ts
import { auth } from "@/auth";

export const runtime = "nodejs";

const BASE = process.env.OSSS_API_BASE_URL ?? "http://127.0.0.1:8081";
const PREFIX = process.env.OSSS_API_PREFIX ?? "/";

async function forward(
  req: Request,
  ctx: { params: Promise<{ path?: string[] }> }
) {
  // Next 15: params is a Promise
  const { path = [] } = await ctx.params;

  // Build upstream URL (preserve query string)
  const incoming = new URL(req.url);
  const joined = (PREFIX + "/" + path.join("/")).replace(/\/+/g, "/");
  const upstream = new URL(joined, BASE);
  upstream.search = incoming.search; // keep ?query=...

  // Pull access token from session
  const session = await auth();
  const accessToken = (session as any)?.accessToken;

  // Prepare headers for upstream (no browser cookies!)
  const headers = new Headers(req.headers);
  headers.delete("cookie");      // don't leak big Auth.js cookies to FastAPI
  headers.delete("host");
  headers.set("accept", "application/json");
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  // Clone body for non-GET/HEAD
  const method = req.method.toUpperCase();
  const body =
    method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();

  const res = await fetch(upstream, {
    method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  });

  // Stream back response
  const resHeaders = new Headers(res.headers);
  resHeaders.delete("content-encoding");
  return new Response(res.body, {
    status: res.status,
    headers: resHeaders,
  });
}

export async function GET(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}
export async function POST(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}
export async function PUT(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}
export async function PATCH(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}
export async function DELETE(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}
export async function HEAD(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}
export async function OPTIONS(req: Request, ctx: { params: Promise<{ path?: string[] }> }) {
  return forward(req, ctx);
}

