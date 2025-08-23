// app/schools/page.tsx
"use client";

import { useState } from "react";

type School = {
  id: string;
  name: string;
  school_code?: string | null;
  nces_school_id?: string | null;
  building_code?: string | null;
  type?: string | null;
  timezone?: string | null;
};

export default function SchoolsPage() {
  const [loading, setLoading] = useState(false);
  const [schools, setSchools] = useState<School[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/osss/schools");
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body?.detail || body?.error || `HTTP ${r.status}`);
      }
      const data = (await r.json()) as School[];
      setSchools(data || []);
    } catch (e: any) {
      setError(e.message || "Failed to load");
      setSchools([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold">Schools</h1>
        <button
          onClick={load}
          disabled={loading}
          className="rounded-lg px-4 py-2 border hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Load Schools"}
        </button>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">
          {error}
        </div>
      )}

      {schools.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left p-2 border">Name</th>
                <th className="text-left p-2 border">Code</th>
                <th className="text-left p-2 border">NCES</th>
                <th className="text-left p-2 border">Building</th>
                <th className="text-left p-2 border">Type</th>
                <th className="text-left p-2 border">Timezone</th>
              </tr>
            </thead>
            <tbody>
              {schools.map((s) => (
                <tr key={s.id} className="even:bg-gray-50">
                  <td className="p-2 border">{s.name}</td>
                  <td className="p-2 border">{s.school_code ?? "—"}</td>
                  <td className="p-2 border">{s.nces_school_id ?? "—"}</td>
                  <td className="p-2 border">{s.building_code ?? "—"}</td>
                  <td className="p-2 border">{s.type ?? "—"}</td>
                  <td className="p-2 border">{s.timezone ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <p className="text-sm text-gray-600">No data yet. Click “Load Schools”.</p>
      )}
    </main>
  );
}
