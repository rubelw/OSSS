import { NextRequest, NextResponse } from "next/server";
import { RASA_URL } from "@/lib/chatProxy";

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return NextResponse.json(
        { error: "Only application/json is accepted" },
        { status: 400 }
      );
    }

    const { text } = await req.json();
    if (!text) {
      return NextResponse.json(
        { error: "Body must include 'text'." },
        { status: 400 }
      );
    }

    const upstream = `${RASA_URL}/model/parse`;
    const upstreamResp = await fetch(upstream, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ text }),
    });

    const raw = await upstreamResp.text();

    if (upstreamResp.status === 404) {
      return NextResponse.json(
        {
          description: "Not Found",
          status: 404,
          message:
            "Rasa NLU endpoint /model/parse not available. Start Rasa with `rasa run --enable-api --enable-nlu` or update your command.",
        },
        { status: 404 }
      );
    }

    try {
      const json = JSON.parse(raw);
      return NextResponse.json(json, { status: upstreamResp.status });
    } catch {
      return new NextResponse(raw, {
        status: upstreamResp.status,
        headers: { "Content-Type": "text/plain" },
      });
    }
  } catch (err: any) {
    console.error("Rasa parse proxy error:", err);
    return NextResponse.json(
      { error: "Rasa parse proxy error", detail: String(err) },
      { status: 500 }
    );
  }
}
