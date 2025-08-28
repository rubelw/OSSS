// src/osss-web/app/pages/api/behaviorcodes.ts
import type { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth";   // ✅ v5 named export
import { authConfig } from "@/app/auth";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // ✅ v5 API only takes the config (no req/res)
  const session = await getServerSession(authConfig); // => Promise<Session | null>

  if (!session?.user) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  return res.status(200).json({ ok: true });
}
