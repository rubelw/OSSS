import { NextRequest, NextResponse } from "next/server";
import {
  tutorUrl,
  SAFE_BASE,
  SAFE_PATH,
  stripGuardNoise,
} from "@/lib/chatProxy";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const contentType = req.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return NextResponse.json(
        { error: "Only application/json is accepted" },
        { status: 400 }
      );
    }

    const body = await req.json();
    const path = `/tutor/tutors/${encodeURIComponent(id)}/chat`;

    // 1) Call upstream Tutor /chat first
    const upstream = tutorUrl(path);
    const tutorResp = await fetch(upstream, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body ?? {}),
    });

    const tutorRaw = await tutorResp.text();

    if (!tutorResp.ok) {
      try {
        return NextResponse.json(JSON.parse(tutorRaw), {
          status: tutorResp.status,
        });
      } catch {
        return new NextResponse(tutorRaw, {
          status: tutorResp.status,
          headers: { "Content-Type": "text/plain" },
        });
      }
    }

    let tutorJson: any;
    try {
      tutorJson = JSON.parse(tutorRaw);
    } catch {
      tutorJson = tutorRaw;
    }

    const candidate =
      tutorJson &&
      typeof tutorJson === "object" &&
      "answer" in tutorJson
        ? String(tutorJson.answer || "")
        : typeof tutorJson === "string"
        ? tutorJson
        : JSON.stringify(tutorJson);

    const sources =
      tutorJson &&
      typeof tutorJson === "object" &&
      Array.isArray(tutorJson.sources)
        ? tutorJson.sources
        : [];

    // 3) Run candidate through guard
    const guardMessages = [
      {
        role: "system",
        content:
          "You are an output safety gateway. If the provided 'candidate' text is safe and compliant, " +
          "return it VERBATIM as your message. If unsafe, refuse with a brief safe alternative.",
      },
      { role: "user", content: `candidate:\n${candidate}` },
    ];

    const safeResp = await fetch(`${SAFE_BASE}${SAFE_PATH}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: req.headers.get("authorization") ?? "",
      },
      body: JSON.stringify({
        model: "llama3.1",
        messages: guardMessages,
        temperature: 0.2,
        max_tokens: 512,
        stream: false,
      }),
    });

    const safeRaw = await safeResp.text();
    let safeJson: any;
    try {
      safeJson = JSON.parse(safeRaw);
    } catch {
      safeJson = undefined;
    }

    if (!safeResp.ok) {
      const reason =
        safeJson?.detail?.reason ||
        safeJson?.detail ||
        safeJson ||
        safeRaw ||
        `HTTP ${safeResp.status}`;
      return NextResponse.json(
        { error: "guard_block", detail: reason },
        { status: safeResp.status }
      );
    }

    let guarded =
      safeJson?.message?.content ??
      safeJson?.choices?.[0]?.message?.content ??
      safeJson?.choices?.[0]?.text ??
      safeRaw;

    guarded = stripGuardNoise(guarded || "");

    // Return Tutor-shaped JSON so ChatClient works unchanged:
    return NextResponse.json(
      { answer: guarded, sources },
      { status: 200 }
    );
  } catch (e: any) {
    console.error("Tutor chat (guarded) proxy error:", e);
    return NextResponse.json(
      { error: "Tutor chat (guarded) proxy error", detail: String(e) },
      { status: 502 }
    );
  }
}
