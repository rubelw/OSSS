"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { AuthButtons } from "@/components/AuthButtons";

type Health = { status: string; realm?: string } | null;

export default function Page() {
  const { data: session, status } = useSession();
  const loggedIn = status === "authenticated";

  const [health, setHealth] = useState<Health>(null);

  const fetchJSON = useCallback(async <T,>(url: string) => {
    const res = await fetch(url, {
      headers: { accept: "application/json" },
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return (await res.json()) as T;
  }, []);

  // Prefetch backend health (once)
  useEffect(() => {
    fetchJSON<Health>("/api/osss/healthz")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, [fetchJSON]);

  const sessionDebug = useMemo(
    () => ({
      status,
      loggedIn,
      user: session?.user ?? null,
      hasAccessToken: Boolean((session as any)?.accessToken),
    }),
    [status, loggedIn, session]
  );

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

      {/* Optional debug panel */}
      <div className="card">
        <h2>Session Debug</h2>
        <pre>{JSON.stringify(sessionDebug, null, 2)}</pre>
      </div>
    </div>
  );
}
