// src/osss-web/app/pages/api/behaviorcodes.ts
import type { NextApiRequest, NextApiResponse } from "next";
import getServerSession from "next-auth";           // ✅ default import in v5
import { authConfig } from "@/app/auth";            // ✅ import config from central file

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const session = await getServerSession(req, res, authConfig);

  if (!session?.user) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  // Example: call your FastAPI upstream using a bearer token if you attach one to the session
  // const accessToken = (session as any).accessToken;
  // const r = await fetch(`${process.env.OSSS_API_URL}/behaviorcodes`, {
  //   headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  // });
  // const data = await r.json();
  // return res.status(r.ok ? 200 : 502).json(data);

  return res.status(200).json({ ok: true });
}
