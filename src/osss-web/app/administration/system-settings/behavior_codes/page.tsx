// src/osss-web/app/behavior-codes/page.tsx
"use client";

import { useState } from "react";

type BehaviorCode = {
  code: string;
  description?: string | null;
};

export default function BehaviorCodesPage() {
  const [loading, setLoading] = useState(false);
  const [codes, setCodes] = useState<BehaviorCode[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/osss/sis/behavior_codes");
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body?.detail || body?.error || `HTTP ${r.status}`);
      }
      const data = (await r.json()) as BehaviorCode[];
      setCodes(data || []);
    } catch (e: any) {
      setError(e.message || "Failed to load");
      setCodes([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold">Behavior Codes</h1>
        <button
          onClick={load}
          disabled={loading}
          className="rounded-lg px-4 py-2 border hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Load Codes"}
        </button>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">
          {error}
        </div>
      )}

      {codes.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left p-2 border">Code</th>
                <th className="text-left p-2 border">Description</th>
              </tr>
            </thead>
            <tbody>
              {codes.map((c) => (
                <tr key={c.code} className="even:bg-gray-50">
                  <td className="p-2 border font-mono">{c.code}</td>
                  <td className="p-2 border">{c.description ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <p className="text-sm text-gray-600">No data yet. Click “Load Codes”.</p>
      )}
    </main>
  );
}
