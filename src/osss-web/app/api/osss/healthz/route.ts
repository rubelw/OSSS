import { NextResponse } from "next/server";

export const dynamic = "force-dynamic"; // no caching

// Optional upstream probe (shown in the JSON, but doesn't affect 200 status)
const BASE = process.env.OSSS_API_BASE_URL || "http://127.0.0.1:8000";
const RAW_PREFIX = process.env.OSSS_API_PREFIX ?? "/";
const PREFIX = RAW_PREFIX.replace(/\/+$/, ""); // trim trailing /
const UPSTREAM_URL = new URL(`${PREFIX}/healthz`.replace(/\/+/g, "/"), BASE).toString();

export async function GET() {
  const started = Date.now();

  let upstream:
    | { url: string; ok: true; status: "ok"; code: number; latency_ms: number }
    | { url: string; ok: false; status: "error" | "unreachable"; code?: number; latency_ms: number };

  try {
    const res = await fetch(UPSTREAM_URL, { cache: "no-store" });
    upstream = {
      url: UPSTREAM_URL,
      ok: res.ok,
      status: res.ok ? "ok" : "error",
      code: res.status,
      latency_ms: Date.now() - started,
    };
  } catch {
    upstream = {
      url: UPSTREAM_URL,
      ok: false,
      status: "unreachable",
      latency_ms: Date.now() - started,
    };
  }

  return NextResponse.json({
    status: "ok",
    app: "osss-web",
    time: new Date().toISOString(),
    upstream,
  });
}

// Nice to have for external health checks
export function HEAD() {
  return new Response(null, { status: 200 });
}
