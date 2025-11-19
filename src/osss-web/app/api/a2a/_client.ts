// app/api/a2a/_client.ts
const A2A_BASE_URL = process.env.A2A_SERVER_URL || "http://localhost:8086";

export async function a2aFetch(path: string, init?: RequestInit) {
  const url = `${A2A_BASE_URL.replace(/\/$/, "")}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`A2A ${path} ${res.status}: ${text}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}
