// app/a2a/admin/page.tsx
"use client";

import { useEffect, useState } from "react";

// read from env
const A2A_BASE =
  process.env.NEXT_PUBLIC_A2A_SERVER_URL || "http://localhost:8086";

type A2AHealth = { ok: boolean; status?: string; error?: string; [k: string]: any };
type A2AAgent = { id: string; name: string; description?: string; [k: string]: any };
type A2ARun = {
  id: string;
  agent_id: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  input_preview?: string;
  output_preview?: string;
  [k: string]: any;
};

export default function A2AAdminPage() {
  const [health, setHealth] = useState<A2AHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const [agents, setAgents] = useState<A2AAgent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);

  const [runs, setRuns] = useState<A2ARun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  const [selectedRun, setSelectedRun] = useState<A2ARun | null>(null);

  const [newAgentId, setNewAgentId] = useState("");
  const [newInput, setNewInput] = useState("");
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  // -------- FETCH HELPERS (direct to A2A server) ----------

  const fetchHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await fetch(`${A2A_BASE}/admin/health`, { cache: "no-store" });
      const data = await res.json();
      setHealth(data);
    } catch (e: any) {
      setHealth({ ok: false, error: String(e?.message || e) });
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchAgents = async () => {
    setAgentsLoading(true);
    try {
      const res = await fetch(`${A2A_BASE}/admin/agents`, { cache: "no-store" });
      const data = await res.json();
      setAgents(Array.isArray(data) ? data : data.agents || []);
    } catch {
      setAgents([]);
    } finally {
      setAgentsLoading(false);
    }
  };

  const fetchRuns = async () => {
    setRunsLoading(true);
    try {
      const res = await fetch(`${A2A_BASE}/admin/runs?limit=50`, { cache: "no-store" });
      const data = await res.json();
      setRuns(Array.isArray(data) ? data : data.runs || []);
    } catch {
      setRuns([]);
    } finally {
      setRunsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    fetchAgents();
    fetchRuns();
  }, []);

  const triggerRun = async () => {
    setTriggerError(null);
    setTriggerLoading(true);
    try {
      const res = await fetch(`${A2A_BASE}/admin/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_id: newAgentId || null,
          input: newInput,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to trigger run");
      setNewInput("");
      fetchRuns();
    } catch (e: any) {
      setTriggerError(String(e?.message || e));
    } finally {
      setTriggerLoading(false);
    }
  };

  // ---------- UI ----------
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">

        {/* Header */}
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs">
                A2A Admin Dashboard
              </span>

            </h1>
            <p className="text-sm text-slate-400">
              Monitor agents, runs, and trigger new conversations.
            </p>
            <p className="text-xs text-slate-500">
              Connected to: {A2A_BASE}
            </p>
          </div>
          <button
            onClick={() => {
              fetchHealth();
              fetchAgents();
              fetchRuns();
            }}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800"
          >
            <span className="text-xs">⟳</span>
            Refresh
          </button>
        </header>

        {/* Top row: health + trigger */}
<div className="grid md:grid-cols-3 gap-4">
  {/* Health */}
  <div className="col-span-1 rounded-xl border border-slate-300 bg-white p-4">
    <div className="flex items-center justify-between mb-2">
      <div className="flex items-center gap-2">
        {/* Simple status dot, color reflects health */}
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            health && health.ok ? "bg-emerald-500" : "bg-red-500"
          }`}
        />
        <span className="text-sm font-medium text-slate-800">
          A2A Health
        </span>
      </div>

      {healthLoading && (
        <div className="h-4 w-4 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" />
      )}
    </div>

    {health ? (
      <div className="space-y-1 text-sm text-slate-700">
        <div>
          Status:{" "}
          <span
            className={
              health.ok
                ? "text-emerald-600 font-semibold"
                : "text-red-600 font-semibold"
            }
          >
            {health.ok ? "OK" : "DOWN"}
          </span>
        </div>

        {health.status && (
          <div className="text-slate-500">
            Detail: {health.status}
          </div>
        )}

        {health.error && (
          <div className="text-xs text-red-600 break-words">
            {health.error}
          </div>
        )}
      </div>
    ) : (
      <div className="text-sm text-slate-500">
        No health data yet.
      </div>
    )}
  </div>

  {/* Trigger new run */}
<div className="col-span-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
  <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-[10px]">
      ▶
    </span>
    Trigger new run
  </div>

  <div className="space-y-2">
    <div className="flex gap-2">
      <select
        value={newAgentId}
        onChange={(e) => setNewAgentId(e.target.value)}
        className="flex-1 rounded-xl bg-slate-950/80 border border-slate-700 px-2 py-1.5 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
      >
        <option value="">Select agent…</option>
        {agents.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name || a.id}
          </option>
        ))}
      </select>
      <button
        onClick={triggerRun}
        disabled={triggerLoading || !newAgentId || !newInput.trim()}
        className="inline-flex items-center gap-1 rounded-xl bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {triggerLoading && (
          <span className="inline-block h-4 w-4 rounded-full border-2 border-slate-100 border-t-transparent animate-spin" />
        )}
        Run
      </button>
    </div>
    <textarea
      value={newInput}
      onChange={(e) => setNewInput(e.target.value)}
      placeholder="Enter prompt / input for the agent…"
      className="w-full h-20 rounded-xl bg-slate-950/80 border border-slate-700 px-2 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
    />
    {triggerError && (
      <div className="text-xs text-red-400 break-words">
        {triggerError}
      </div>
    )}
  </div>
</div>
</div>

{/* Agents & runs */}
<div className="grid md:grid-cols-3 gap-4">
  {/* Agents list */}
  <div className="col-span-1 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
    <div className="flex items-center justify-between mb-2">
      <span className="text-sm font-medium text-slate-100">Agents</span>
      {agentsLoading && (
        <span className="inline-block h-3 w-3 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" />
      )}
    </div>
    <div className="space-y-2 max-h-72 overflow-y-auto pr-1 text-sm">
      {agents.length === 0 && (
        <div className="text-slate-500 text-xs">
          No agents reported. Check <code>/admin/agents</code> on the A2A server.
        </div>
      )}
      {agents.map((agent) => (
        <button
          key={agent.id}
          onClick={() => setNewAgentId(agent.id)}
          className={`w-full text-left rounded-xl px-2 py-1.5 border ${
            newAgentId === agent.id
              ? "border-sky-500 bg-slate-800"
              : "border-slate-800 hover:bg-slate-900"
          }`}
        >
          <div className="font-medium text-slate-100">
            {agent.name || agent.id}
          </div>
          {agent.description && (
            <div className="text-xs text-slate-400 line-clamp-2">
              {agent.description}
            </div>
          )}
        </button>
      ))}
    </div>
  </div>

  {/* Runs table */}
  <div className="col-span-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
    <div className="flex items-center justify-between mb-2">
      <span className="text-sm font-medium text-slate-100">Recent runs</span>
      {runsLoading && (
        <span className="inline-block h-3 w-3 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" />
      )}
    </div>
    <div className="border border-slate-800 rounded-xl overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-slate-950/60 text-slate-400">
          <tr>
            <th className="px-2 py-1 text-left">ID</th>
            <th className="px-2 py-1 text-left">Agent</th>
            <th className="px-2 py-1 text-left">Status</th>
            <th className="px-2 py-1 text-left">Created</th>
            <th className="px-2 py-1 text-left">Output</th>
          </tr>
        </thead>
        <tbody>
          {runs.length === 0 && (
            <tr>
              <td
                colSpan={5}
                className="px-2 py-3 text-center text-slate-500"
              >
                No runs yet.
              </td>
            </tr>
          )}
          {runs.map((run) => (
            <tr
              key={run.id}
              className="border-t border-slate-800 hover:bg-slate-800/60 cursor-pointer"
              onClick={() => setSelectedRun(run)}
            >
              <td className="px-2 py-1 font-mono truncate max-w-[140px] text-slate-100">
                {run.id}
              </td>
              <td className="px-2 py-1 text-slate-100">
                {run.agent_id}
              </td>
              <td className="px-2 py-1">
                <span
                  className={
                    run.status === "succeeded"
                      ? "text-emerald-400"
                      : run.status === "failed"
                      ? "text-red-400"
                      : "text-slate-300"
                  }
                >
                  {run.status}
                </span>
              </td>
              <td className="px-2 py-1 text-slate-400">
                {run.created_at || "-"}
              </td>
              <td className="px-2 py-1 text-slate-400 truncate max-w-[180px]">
                {run.output_preview || run.input_preview || ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    {/* Run detail drawer */}
    {selectedRun && (
      <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/80 p-3 space-y-2 text-xs text-slate-100">
        <div className="flex justify-between items-center">
          <div className="font-medium">
            Run detail – {selectedRun.id}
          </div>
          <button
            onClick={() => setSelectedRun(null)}
            className="text-slate-400 hover:text-slate-200 text-xs"
          >
            Close
          </button>
        </div>
        <pre className="bg-slate-900/80 rounded-lg p-2 max-h-64 overflow-y-auto whitespace-pre-wrap text-[11px]">
          {JSON.stringify(selectedRun, null, 2)}
        </pre>
      </div>
    )}
  </div>
</div>



        {/* Health, Trigger, Agents, Runs, Drawer */}
        {/* (Your existing UI continues below) */}

      </div>
    </div>
  );


}
