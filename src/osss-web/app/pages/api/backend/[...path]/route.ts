// src/osss-web/app/pages/api/backend/[...path]/route.ts
import { NextResponse, type NextRequest } from "next/server";
import { auth } from "@/app/auth";   // ✅ fixed import, uses alias (preferred)

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> } // ✅ correct typing (params is Promise)
) {
  const { path } = await context.params;
  const session = await auth();

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Example passthrough logic — forward to backend
  const targetUrl = `${process.env.OSSS_API_URL}/${path.join("/")}`;
  const res = await fetch(targetUrl, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${(session as any).accessToken}`,
    },
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
