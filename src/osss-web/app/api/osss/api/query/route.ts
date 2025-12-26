import { NextResponse } from "next/server";

export const runtime = "nodejs"; // IMPORTANT: avoid edge runtime for long calls
export const dynamic = "force-dynamic";

const UPSTREAM = process.env.CHAT_UPSTREAM_BASE ?? "http://app:8000"; // server-only env
const UPSTREAM_URL = `${UPSTREAM}/api/query`;

export async function POST(req: Request) {
  const body = await req.text();

  // You can set a high timeout here if you want:
  const controller = new AbortController();
  const timeoutMs = 180_000; // 3 min
  const t = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const upstreamResp = await fetch(UPSTREAM_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body,
      signal: controller.signal,
      // keepalive is browser-only; not needed here
    });

    const text = await upstreamResp.text();
    return new NextResponse(text, {
      status: upstreamResp.status,
      headers: {
        "Content-Type": upstreamResp.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (e: any) {
    const msg =
      e?.name === "AbortError"
        ? `Upstream timed out after ${timeoutMs}ms`
        : `Upstream error: ${String(e)}`;

    return NextResponse.json({ error_message: msg }, { status: 504 });
  } finally {
    clearTimeout(t);
  }
}
