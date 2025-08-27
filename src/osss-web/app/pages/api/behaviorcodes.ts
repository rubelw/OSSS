import type { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "./auth/[...nextauth]";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8081";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const session = await getServerSession(req, res, authOptions);
  const token = (session as any)?.accessToken;
  if (!token) return res.status(401).json({ detail: "Not authenticated" });

  const r = await fetch(`${API_BASE}/api/behaviorcodes`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const text = await r.text();
  res.status(r.status).send(text);
}
