// app/api/diag/redis/route.ts
import { NextResponse } from "next/server";
import { Redis } from "@upstash/redis";

export async function GET() {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) {
    return NextResponse.json({ ok: false, reason: "Missing Upstash env vars" }, { status: 500 });
  }
  const redis = new Redis({ url, token });
  const pong = await redis.ping(); // "PONG"
  return NextResponse.json({ ok: true, pong });
}
