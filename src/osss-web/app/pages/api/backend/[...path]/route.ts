import { NextRequest, NextResponse } from "next/server";
import { auth } from "../../../auth";

const BASE = process.env.OSSS_API_URL || "http://127.0.0.1:8081";

function buildTargetURL(pathSegments: string[] | undefined, search: string) {
  const path = pathSegments?.join("/") ?? "";
  return `${BASE}/${path}${search ? `?${search}` : ""}`;
}

async function forward(
  req: NextRequest,
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  params: { path?: string[] }
) {
  const url = buildTargetURL(params.path, req.nextUrl.searchParams.toString());
  const session = await auth();

  const headers = new Headers();
  // pass content-type if present
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  headers.set("accept", "application/json");

  // attach bearer if logged in
  const accessToken = (session as any)?.accessToken as string | undefined;
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const body = ["POST", "PUT", "PATCH"].includes(method) ? await req.text() : undefined;

  const res = await fetch(url, { method, headers, body, cache: "no-store" });
  const out = await res.text();
  return new NextResponse(out, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return forward(req, "GET", ctx.params);
}
export async function POST(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return forward(req, "POST", ctx.params);
}
export async function PUT(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return forward(req, "PUT", ctx.params);
}
export async function PATCH(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return forward(req, "PATCH", ctx.params);
}
export async function DELETE(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return forward(req, "DELETE", ctx.params);
}
