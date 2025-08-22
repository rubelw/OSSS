import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.OSSS_API_URL || "http://localhost:8000";

function buildTargetURL(pathSegments: string[] | undefined, search: string) {
  const path = pathSegments?.join("/") ?? "";
  return `${BASE}/${path}${search ? `?${search}` : ""}`;
}

export async function GET(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const url = buildTargetURL(params?.path, req.nextUrl.searchParams.toString());
  const res = await fetch(url, { headers: { "accept": "application/json" }, cache: "no-store" });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" }
  });
}

export async function POST(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const url = buildTargetURL(params?.path, req.nextUrl.searchParams.toString());
  const body = await req.text();
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": req.headers.get("content-type") ?? "application/json" },
    body
  });
  const out = await res.text();
  return new NextResponse(out, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" }
  });
}

export async function PUT(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const url = buildTargetURL(params?.path, req.nextUrl.searchParams.toString());
  const body = await req.text();
  const res = await fetch(url, {
    method: "PUT",
    headers: { "content-type": req.headers.get("content-type") ?? "application/json" },
    body
  });
  const out = await res.text();
  return new NextResponse(out, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" }
  });
}

export async function DELETE(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const url = buildTargetURL(params?.path, req.nextUrl.searchParams.toString());
  const res = await fetch(url, { method: "DELETE" });
  const out = await res.text();
  return new NextResponse(out, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" }
  });
}
