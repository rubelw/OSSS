// app/components/SessionDebugClaims.tsx
"use client";

import { useEffect, useState } from "react";

export default function SessionDebugClaims() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch("/api/kc/claims", { cache: "no-store" });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`${res.status} ${res.statusText}: ${t}`);
      }
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Auto-load once; or remove this and load on button click only
    load();
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button onClick={load} className="btn" disabled={loading}>
          {loading ? "Loading…" : "Reload KC details"}
        </button>
        {err && <span className="text-red-600 text-sm">{err}</span>}
      </div>

      {data && (
        <pre className="p-3 bg-gray-100 rounded text-xs overflow-auto">
{JSON.stringify(
  {
    realmRoles: data.realmRoles,
    clientRoles: data.clientRoles,
    attributes: data.attributes,
    // comment out next line if the blob is too big for your UI:
    claims: data.claims,
  },
  null,
  2
)}
        </pre>
      )}
    </div>
  );
}
