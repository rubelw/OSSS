import { NextRequest, NextResponse } from "next/server";
import { SAFE_BASE, SAFE_PATH } from "@/lib/chatProxy";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    if (!body || !Array.isArray(body.messages) || body.messages.length === 0) {
      return NextResponse.json(
        { error: "Request must include messages array" },
        { status: 400 }
      );
    }

    const upstream = `${SAFE_BASE}${SAFE_PATH}`;
    const upstreamResp = await fetch(upstream, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: req.headers.get("authorization") ?? "",
      },
      body: JSON.stringify(body),
    });

    const raw = await upstreamResp.text();

    try {
      const json = JSON.parse(raw);
      return NextResponse.json(json, { status: upstreamResp.status });
    } catch {
      return new NextResponse(raw, {
        status: upstreamResp.status,
        headers: {
          "Content-Type":
            upstreamResp.headers.get("content-type") ?? "text/plain",
        },
      });
    }
  } catch (err: any) {
    console.error("chat safe proxy error:", err);
    return NextResponse.json(
      { error: "Proxy error", detail: String(err) },
      { status: 500 }
    );
  }
}
