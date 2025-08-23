"use client";

import { useState } from "react";
type Event = {
  id: string;
  title: string;
  summary?: string | null;
  starts_at: string;
  ends_at?: string | null;
  venue?: string | null;
  status: string;
};

export default function EventsPage() {
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/osss/events");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as Event[];
      setEvents(data);
    } catch (e: any) {
      setError(e.message || "Failed to load");
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="content">
      <div className="page-head">
        <h1>Events</h1>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Load Events"}
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      {events.length ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>When</th>
                <th>Venue</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{e.title}</td>
                  <td>
                    {new Date(e.starts_at).toLocaleString()}
                    {e.ends_at ? ` – ${new Date(e.ends_at).toLocaleString()}` : ""}
                  </td>
                  <td>{e.venue ?? "—"}</td>
                  <td>{e.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : !loading ? (
        <p className="muted">No events yet. Click “Load Events”.</p>
      ) : null}
    </main>
  );
}
