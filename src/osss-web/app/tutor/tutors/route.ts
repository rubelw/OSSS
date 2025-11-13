import { NextRequest, NextResponse } from "next/server";
import { tutorUrl } from "@/lib/chatProxy";

// GET /tutor/tutors
export async function GET() {
  try {
    const upstream = tutorUrl("/tutor/tutors");
    const r = await fetch(upstream, {
      headers: { Accept: "application/json" },
    });
    const raw = await r.text();
    try {
      const json = JSON.parse(raw);
      return NextResponse.json(json, { status: r.status });
    } catch {
      return new NextResponse(raw, {
        status: r.status,
        headers: { "Content-Type": "text/plain" },
      });
    }
  } catch (e: any) {
    console.error("Tutor list proxy error:", e);
    return NextResponse.json(
      { error: "Tutor proxy error", detail: String(e) },
      { status: 502 }
    );
  }
}

// POST /tutor/tutors (upsert)
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const upstream = tutorUrl("/tutor/tutors");
    const r = await fetch(upstream, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
    const raw = await r.text();
    try {
      const json = JSON.parse(raw);
      return NextResponse.json(json, { status: r.status });
    } catch {
      return new NextResponse(raw, {
        status: r.status,
        headers: { "Content-Type": "text/plain" },
      });
    }
  } catch (e: any) {
    console.error("Tutor upsert proxy error:", e);
    return NextResponse.json(
      { error: "Tutor proxy error", detail: String(e) },
      { status: 502 }
    );
  }
}
