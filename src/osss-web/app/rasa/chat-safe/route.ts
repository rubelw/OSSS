import { NextRequest, NextResponse } from "next/server";
import {
  RASA_URL,
  SAFE_BASE,
  SAFE_PATH,
  joinRasaBubbles,
  stripGuardNoise,
} from "@/lib/chatProxy";

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return NextResponse.json(
        { error: "Only application/json is accepted" },
        { status: 400 }
      );
    }

    const { sender, message, metadata } = await req.json();
    if (!message) {
      return NextResponse.json(
        { error: "Body must include 'message'." },
        { status: 400 }
      );
    }

    // 1) Ask Rasa first
    const rasaPayload = {
      sender: sender || "user",
      message,
      ...(metadata ? { metadata } : {}),
    };

    const rasaResp = await fetch(
      `${RASA_URL}/webhooks/rest/webhook`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(rasaPayload),
      }
    );

    const rasaRaw = await rasaResp.text();

    if (!rasaResp.ok) {
      try {
        return NextResponse.json(JSON.parse(rasaRaw), {
          status: rasaResp.status,
        });
      } catch {
        return new NextResponse(rasaRaw, {
          status: rasaResp.status,
          headers: { "Content-Type": "text/plain" },
        });
      }
    }

    // 2) Normalize Rasa bubbles into one candidate reply
    const candidate = joinRasaBubbles(rasaRaw) || "";

    // 3) Send candidate through guard
    // const guardMessages = [
    //  {
    //    role: "system",
    //    content:
    //      "You are an output safety gateway. If the provided 'candidate' text is safe and compliant, " +
    //      "return it VERBATIM as your message. If unsafe, refuse with a brief safe alternative.",
    //  },
    //  { role: "user", content: `candidate:\n${candidate}` },
    // ];

    // const safeResp = await fetch(`${SAFE_BASE}${SAFE_PATH}`, {
    //   method: "POST",
    //   headers: {
    //     Accept: "application/json",
    //     "Content-Type": "application/json",
    //     Authorization: req.headers.get("authorization") ?? "",
    //   },
    //   body: JSON.stringify({
    //     model: "llama3.1",
    //     messages: guardMessages,
    //     temperature: 0.2,
    //     max_tokens: 512,
    //     stream: false,
    //   }),
    // });

    // const safeRaw = await safeResp.text();
    // let safeJson: any;
    // try {
    //   safeJson = JSON.parse(safeRaw);
    // } catch {
    //   safeJson = undefined;
    // }

    // if (!safeResp.ok) {
    //   const reason =
    //     safeJson?.detail?.reason ||
    //     safeJson?.detail ||
    //     safeJson ||
    //     safeRaw ||
    //     `HTTP ${safeResp.status}`;
    //   return NextResponse.json(
    //     { error: "guard_block", detail: reason },
    //     { status: safeResp.status }
    //   );
    // }

    // let guarded =
    //   safeJson?.message?.content ??
    //   safeJson?.choices?.[0]?.message?.content ??
    //   safeJson?.choices?.[0]?.text ??
    //   safeRaw;

    // guarded = stripGuardNoise(guarded || "");

    // ChatClient expects Rasa-like array: [{ recipient_id, text }]
    // return NextResponse.json(
    //   [{ recipient_id: sender || "user", text: guarded }],
    //   { status: 200 }
    // );

    // 3) Return Rasa's candidate directly (no guard)
    return NextResponse.json(
      [
        {
          recipient_id: sender || "user",
          text: candidate,
        },
      ],
      { status: 200 }
    );


  } catch (err: any) {
    console.error("Rasa chat-safe proxy error:", err);
    return NextResponse.json(
      { error: "Rasa chat-safe proxy error", detail: String(err) },
      { status: 500 }
    );
  }
}
