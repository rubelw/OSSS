"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { AuthButtons } from "@/components/AuthButtons";

type Health = { status: string; realm?: string } | null;
type StateItem = { code: string; name: string };

export default function Page() {
  const { data: session, status } = useSession();
  const loggedIn = status === "authenticated";

  const [health, setHealth] = useState<Health>(null);
  const [states, setStates] = useState<StateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // small helper
  async function fetchJSON(url: string) {
    const res = await fetch(url, {
      headers: { accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  // Prefetch health
  useEffect(() => {
    fetchJSON("/api/osss/healthz")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // Load states via Next.js API proxy (adds Authorization: Bearer …)
  const loadStates = async () => {
    if (!loggedIn) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJSON("/api/osss/states");
      setStates(data as StateItem[]);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load states");
      setStates([]);
    } finally {
      setLoading(false);
    }
  };

  // Optional: auto-load after successful login
  useEffect(() => {
    if (loggedIn) void loadStates();
  }, [loggedIn]);

  return (
    <div className="container">
      {/* Top bar with Auth buttons */}
      <div className="flex items-center justify-between mb-6">
        <h1>OSSS Web</h1>
        <AuthButtons />
      </div>

      <p className="text-muted-foreground">
        Minimal frontend talking to the OSSS FastAPI backend via Next.js API
        routes with bearer auth.
      </p>

      <div className="card">
        <h2>Backend Health</h2>
        <pre>{JSON.stringify(health ?? { status: "unknown" }, null, 2)}</pre>
      </div>

      <div className="card">
  <h2>States</h2>

  <div className="flex items-center gap-3 mb-2">
    <button
      type="button"
      className="btn"
      disabled={!loggedIn || loading}
      onClick={() => {
        if (!loggedIn || loading) return; // extra guard
        void loadStates();                // call only on explicit click
      }}
    >
      {loading ? "Loading…" : loggedIn ? "Load States" : "Login to load states"}
    </button>

    {!loggedIn && (
      <span className="text-sm text-muted-foreground"></span>
    )}
  </div>

  {error && <p style={{ color: "#ff6b6b" }}>Error: {error}</p>}

  <pre>
    {Array.isArray(states) && states.length > 0
      ? JSON.stringify(states, null, 2)
      : "No data yet."}
  </pre>
</div>

      {/* Optional debug panel */}
      <div className="card">
        <h2>Session Debug</h2>
        <pre>
          {JSON.stringify(
            {
              loggedIn,
              user: session?.user ?? null,
              hasAccessToken: Boolean((session as any)?.accessToken),
            },
            null,
            2
          )}
        </pre>
      </div>
    </div>
  );
}
