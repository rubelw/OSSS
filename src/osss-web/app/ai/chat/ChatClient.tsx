"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";

// Reference the image from the public folder
const uploadIcon = "/add.png"; // Path from public directory

// Note: fetch has no timeout by default; this makes it explicit.
const CLIENT_QUERY_TIMEOUT_MS = 180_000; // 3 minutes

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
  fullWidth?: boolean; // 👈 NEW
  // 👇 NEW: raw metadata from backend, if any
  meta?: any;
}

interface RetrievedChunk {
  source?: string;
  score?: number;
  filename?: string;
  chunk_index?: number;
  text_preview?: string;
  image_paths?: string[] | null;
  page_index?: number | null;
  page_chunk_index?: number | null;
  pdf_index_path?: string | null;
}

function prettyJson(raw: string): string {
  try {
    const obj = JSON.parse(raw);
    return JSON.stringify(obj, null, 2);
  } catch {
    return raw;
  }
}

// Strip PII / link-like content from TEXT that goes back into chatHistory
function sanitizeForGuard(src: string): string {
  let t = src;

  // Collapse whitespace
  t = t.replace(/\s+/g, " ").trim();

  // Emails
  t = t.replace(/\S+@\S+\b/g, "[redacted email]");

  // URLs (so they don't end up in chatHistory)
  t = t.replace(/https?:\/\/\S+/gi, "[redacted url]");

  // Markdown-style links [text](url) -> keep just the text
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");

  // Phone-like patterns (rough)
  t = t.replace(/\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g, "[redacted phone]");

  return t;
}

type WorkflowResponse = {
  workflow_id?: string;
  status?: string;
  agent_outputs?: Record<string, any>;
  agent_output_meta?: any;
  markdown_export?: { file_path?: string; filename?: string; error?: string } | null;
  execution_time_seconds?: number;
  correlation_id?: string;
  error_message?: string | null;
  answer?: string;

  // ✅ top-level conversation id (matches your raw JSON)
  conversation_id?: string;

  execution_state?: {
    // ✅ mirrored here if server sets it
    conversation_id?: string;
    final?: {
      final_answer?: string;
      used_rag?: boolean;
      rag_excerpt?: string;
      sources_used?: string[];
      timestamp?: string;
    };
    structured_outputs?: {
      final?: {
        final_answer?: string;
        used_rag?: boolean;
        rag_excerpt?: string;
        sources_used?: string[];
        timestamp?: string;
      };
    };
  };

  workflow_result?: {
    structured_outputs?: {
      final?: {
        final_answer?: string;
        used_rag?: boolean;
        rag_excerpt?: string;
        sources_used?: string[];
        timestamp?: string;
      };
    };
  };
};


function looksLikeLLMResponseWrapper(text: string): boolean {
  return /^LLMResponse\(text=/.test(text.trim());
}

function pickFinalAnswer(wf: WorkflowResponse): string {
  // 🔹 1) Prefer canonical final_answer from execution_state / structured_outputs
  const es: any = wf.execution_state || {};
  const fromExecState =
    es.final?.final_answer ??
    es.structured_outputs?.final?.final_answer ??
    wf.workflow_result?.structured_outputs?.final?.final_answer;

  if (typeof fromExecState === "string" && fromExecState.trim()) {
    return fromExecState;
  }

  // 🔹 2) If top-level answer exists and is not just an LLMResponse(...) debug wrapper, use it
  if (
    typeof wf.answer === "string" &&
    wf.answer.trim() &&
    !looksLikeLLMResponseWrapper(wf.answer)
  ) {
    return wf.answer;
  }

  // 🔹 3) Last resort: old behavior (look at agent_outputs.final / refiner / first string)
  return pickPrimaryText(wf.agent_outputs);
}

function pickPrimaryText(agentOutputs: Record<string, any> | undefined): string {
  if (!agentOutputs) return "";

  // Prioritize the final output if available
  const finalOutput = agentOutputs.final;
  if (typeof finalOutput === "string" && finalOutput.trim()) return finalOutput;

  // Fallback to the refiner output if no final output
  const refinerOutput = agentOutputs.refiner;
  if (typeof refinerOutput === "string" && refinerOutput.trim()) return refinerOutput;

  // fallback: first string value
  for (const k of Object.keys(agentOutputs)) {
    const v = agentOutputs[k];
    if (typeof v === "string" && v.trim()) return v;
  }
  return "";
}

function getQueryProfile(payload: any) {
  return payload?.agent_output_meta?._query_profile ?? null;
}

/**
 * Very small Markdown → HTML helper:
 * - code blocks
 * - inline code
 * - links
 * - bold
 * - bullet lists starting with `* ` or `- `
 *   (even if they originally appeared inline, like `: * item1 * item2`)
 */
function mdToHtml(src: string): string {
  // Escape HTML
  let s = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // --- Normalize inline bullets into real lines --------------------
  s = s.replace(/([^\n])\s+\*(\s+)/g, "$1\n*$2");

  // Code blocks
  s = s.replace(/```([\s\S]*?)```/g, (_m, code) => {
    return `<pre><code>${code.replace(/&/g, "&amp;")}</code></pre>`;
  });

  // Inline code
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Markdown links
  s = s.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
  );

  // Bold
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // --- Line-based processing: lists + tables -----------------------
  const lines = s.split(/\n/);
  let inList = false;
  const out: string[] = [];

  const isTableSeparator = (line: string): boolean => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("|")) return false;
    // something like: | --- | --- | --- |
    return /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(trimmed);
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // --- TABLE DETECTION -------------------------------------------
    const trimmed = line.trim();
    const looksLikeTableRow = trimmed.startsWith("|") && trimmed.includes("|");

    // Header + separator = start of table
    if (looksLikeTableRow && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      // Close any open list before starting table
      if (inList) {
        out.push("</ul>");
        inList = false;
      }

      // Header row
      const headerCells = trimmed
        .replace(/^\||\|$/g, "") // strip leading/trailing |
        .split("|")
        .map((c) => c.trim());

      out.push('<table class="md-table"><thead><tr>');
      headerCells.forEach((cell) => out.push(`<th>${cell}</th>`));
      out.push("</tr></thead><tbody>");

      // Skip the separator line
      i += 1;

      // Data rows
      while (i + 1 < lines.length) {
        const next = lines[i + 1];
        const nextTrimmed = next.trim();
        if (!(nextTrimmed.startsWith("|") && nextTrimmed.includes("|"))) break;

        i += 1;
        const rowCells = nextTrimmed
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((c) => c.trim());

        out.push("<tr>");
        rowCells.forEach((cell) => out.push(`<td>${cell}</td>`));
        out.push("</tr>");
      }

      out.push("</tbody></table>");
      continue;
    }

    // --- BULLET LIST HANDLING --------------------------------------
    const bulletMatch = line.match(/^\s*([*-])\s+(.+)/);

    if (bulletMatch) {
      const itemText = bulletMatch[2];
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${itemText}</li>`);
    } else {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      if (line.trim().length > 0) out.push(`${line}<br/>`);
      else out.push("<br/>");
    }
  }

  if (inList) out.push("</ul>");

  return out.join("");
}

/**
 * Build an HTML "Sources" block appended to the bot reply,
 * with direct links to /rag-pdfs/main/<filename>.
 */
function buildSourcesHtmlFromChunks(chunks: RetrievedChunk[]): string {
  if (!chunks || chunks.length === 0) return "";

  const items: string[] = [];

  for (const c of chunks) {
    // 👇 centralize how we compute the source path
    const sourcePath: string | undefined =
      (c as any).pdf_index_path || (c as any).source || c.filename || undefined;

    if (!sourcePath) continue;

    // Encode each path segment so `/` stays as `/`
    const safeSegments = sourcePath.split("/").map((seg) => encodeURIComponent(seg));
    const href = `/rag-pdfs/main/${safeSegments.join("/")}`;

    // Shown text: just the last part
    const displayName = sourcePath.split("/").pop() || c.filename || "Unknown file";

    const metaParts: string[] = [];
    if (typeof c.page_index === "number") metaParts.push(`page ${c.page_index + 1}`);
    if (typeof c.score === "number") metaParts.push(`score ${c.score.toFixed(3)}`);

    const meta = metaParts.length > 0 ? ` – ${metaParts.join(" – ")}` : "";

    items.push(
      `<li><a href="${href}" target="_blank" rel="noreferrer">${displayName}</a>${meta}</li>`
    );
  }

  if (!items.length) return "";

  return `
    <div class="rag-sources" style="margin-top:12px;">
      <div style="font-weight:bold;margin-bottom:4px;">Sources</div>
      <ul style="padding-left:16px;margin:0;">
        ${items.join("\n")}
      </ul>
    </div>
  `;
}

/**
 * 🔹 PREVIOUS: build markdown tables from data_query rows.
 * We’ll now treat this as a **fallback** when the backend does NOT
 * provide table_markdown_compact / table_markdown_full.
 */
function buildDataQueryMarkdown(agentOutputs?: Record<string, any>): string {
  if (!agentOutputs) return "";

  const blocks: string[] = [];

  for (const [key, value] of Object.entries(agentOutputs)) {
    if (!key.startsWith("data_query")) continue;
    if (!value || typeof value !== "object") continue;

    // If new-style output with table_markdown_* exists, skip here
    const v: any = value;
    if (v.table_markdown_compact || v.table_markdown_full) continue;

    const dq = value as {
      view?: string;
      ok?: boolean;
      rows?: any[];
      row_count?: number;
    };

    if (dq.ok !== true) continue;
    if (!Array.isArray(dq.rows) || dq.rows.length === 0) continue;

    const rows = dq.rows;
    const viewName = dq.view || key;

    // Collect columns from all rows (union), so we don't drop fields
    const colSet = new Set<string>();
    for (const r of rows) {
      if (r && typeof r === "object") {
        Object.keys(r).forEach((c) => colSet.add(c));
      }
    }
    const cols = Array.from(colSet);
    if (cols.length === 0) continue;

    const lines: string[] = [];

    lines.push(`**Data query: ${viewName}**`);
    if (typeof dq.row_count === "number") {
      lines.push(`_Rows: ${dq.row_count}_`);
    }
    lines.push(""); // blank line before table

    // Header
    lines.push(`| ${cols.join(" | ")} |`);
    lines.push(`| ${cols.map(() => "---").join(" | ")} |`);

    // Rows
    for (const row of rows) {
      const cells = cols.map((col) => {
        const v = row?.[col];
        if (v === null || v === undefined) return "";
        if (typeof v === "object") {
          try {
            return JSON.stringify(v);
          } catch {
            return String(v);
          }
        }
        return String(v);
      });
      lines.push(`| ${cells.join(" | ")} |`);
    }

    lines.push(""); // trailing blank line
    blocks.push(lines.join("\n"));
  }

  return blocks.join("\n\n---\n\n");
}

/**
 * 🔹 NEW: extract first data_query canonical output that has
 * table_markdown_compact / table_markdown_full.
 */
function extractDataQueryMeta(agentOutputs?: Record<string, any>): any | null {
  if (!agentOutputs) return null;
  for (const [key, value] of Object.entries(agentOutputs)) {
    if (!key.startsWith("data_query")) continue;
    if (!value || typeof value !== "object") continue;

    const v: any = value;
    if (v.table_markdown_compact || v.table_markdown_full) {
      return v;
    }
  }
  return null;
}

/**
 * Map the raw intent label to a more descriptive explanation.
 * This is aligned with server-side intents.
 */
function describeIntent(intent: string): string {
  switch (intent) {
    case "superintendent":
      return "district leadership / superintendent communications";
    case "superintendent_goals":
      return "superintendent goals and accountability";
    case "principal":
      return "building-level leadership / principal perspective";
    case "teacher":
      return "classroom-level / teacher perspective";
    case "student":
      return "student reflection / student help";
    case "parent":
      return "family or guardian perspective";
    // ... (rest unchanged)
    case "general":
    default:
      return "general information / mixed audience";
  }
}

/**
 * 🔹 NEW: UI component for data_query results with compact/full toggle.
 */
type ProjectionMode = "compact" | "full";

function DataQueryResult({ meta }: { meta: any }) {
  const [mode, setMode] = useState<ProjectionMode>(
    (meta?.projection_mode as ProjectionMode) || "compact"
  );

  const hasCompact = !!meta?.table_markdown_compact;
  const hasFull = !!meta?.table_markdown_full;

  if (!hasCompact && !hasFull) return null;

  const markdown =
    mode === "full"
      ? meta.table_markdown_full || meta.table_markdown_compact
      : meta.table_markdown_compact || meta.table_markdown_full;

  const html = mdToHtml(String(markdown || ""));

  return (
    <div className="data-query-result" style={{ marginTop: "8px" }}>
      <div className="flex justify-between items-center mb-2">
        <div className="text-sm text-gray-500">
          {meta?.entity?.display_name || meta?.view || "Query result"}
        </div>

        {hasCompact && hasFull && (
          <div className="flex gap-2 text-xs">
            <button
              type="button"
              onClick={() => setMode("compact")}
              style={{
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid #ccc",
                backgroundColor: mode === "compact" ? "#f0f0f0" : "transparent",
                cursor: "pointer",
              }}
            >
              Compact view
            </button>
            <button
              type="button"
              onClick={() => setMode("full")}
              style={{
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid #ccc",
                backgroundColor: mode === "full" ? "#f0f0f0" : "transparent",
                cursor: "pointer",
              }}
            >
              Full view
            </button>
          </div>
        )}
      </div>

      <div
        className="data-query-table"
        style={{ overflowX: "auto", fontSize: "0.85rem" }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}


export default function ChatClient() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [lastRawResponse, setLastRawResponse] = useState<string>("");

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant" | "system"; content: string }[]
  >([]);

  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [uploadedFilesNames, setUploadedFilesNames] = useState<string[]>([]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [retrievedChunks, setRetrievedChunks] = useState<RetrievedChunk[]>([]);

  const [showDebug, setShowDebug] = useState<boolean>(false);

  // NEW: toggle "Sources" block on/off
  const [showSources, setShowSources] = useState<boolean>(true);

  // main RAG session id (per tab)
  const [sessionId, setSessionId] = useState<string>(() => {
    let initial = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    if (typeof window !== "undefined") {
      try {
        const stored = window.sessionStorage.getItem("osss_chat_session_id");
        if (stored && typeof stored === "string") return stored;

        if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
          initial = crypto.randomUUID();
        }
        window.sessionStorage.setItem("osss_chat_session_id", initial);
      } catch {
        // ignore storage errors
      }
    }

    return initial;
  });

  // 🔹 NEW: conversation id state, persisted in sessionStorage
  const [conversationId, setConversationId] = useState<string | null>(() => {
      if (typeof window === "undefined") return null;
      try {
        const stored = window.sessionStorage.getItem("osss_conversation_id");
        return stored || null;
      } catch {
        return null;
      }
    });

  // NEW: subagent session id (e.g. registration workflow)
  const [subagentSessionId, setSubagentSessionId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const handleExitSubagent = useCallback(async () => {
    if (!subagentSessionId) return;

    try {
      await fetch(`${API_BASE}/ai/chat/subagent/reset`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          agent_session_id: sessionId,
          subagent_session_id: subagentSessionId,
        }),
      });
    } catch (err) {
      console.error("Failed to reset subagent session", err);
    } finally {
      setSubagentSessionId(null);
    }
  }, [sessionId, subagentSessionId]);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const fileArray = Array.from(files);
      setUploadedFiles((prevFiles) => [...prevFiles, ...fileArray]);
      const fileNames = fileArray.map((file) => file.name);
      setUploadedFilesNames((prevNames) => [...prevNames, ...fileNames]);
    }
  };

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  // On mount: restore messages & history & conversationId (defensive)
  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      const storedMessages = window.sessionStorage.getItem("osss_chat_messages");
      if (storedMessages) setMessages(JSON.parse(storedMessages) as UiMessage[]);

      const storedHistory = window.sessionStorage.getItem("osss_chat_history");
      if (storedHistory) {
        setChatHistory(
          JSON.parse(storedHistory) as {
            role: "user" | "assistant" | "system";
            content: string;
          }[]
        );
      }

      const storedSession = window.sessionStorage.getItem("osss_chat_session_id");
      if (storedSession) {
        setSessionId(storedSession);
      } else {
        let initial = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        if (typeof crypto !== "undefined" && "randomUUID" in crypto) initial = crypto.randomUUID();
        window.sessionStorage.setItem("osss_chat_session_id", initial);
        setSessionId(initial);
      }

      const storedConversationId = window.sessionStorage.getItem("osss_conversation_id");
      if (storedConversationId) {
        setConversationId(storedConversationId);
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  // Persist messages
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem("osss_chat_messages", JSON.stringify(messages));
    } catch {}
  }, [messages]);

  // Persist chat history
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem("osss_chat_history", JSON.stringify(chatHistory));
    } catch {}
  }, [chatHistory]);

  // 👇 UPDATED: appendMessage now accepts optional meta
  const appendMessage = useCallback(
    (
      who: "user" | "bot",
      content: string,
      isHtml = false,
      fullWidth = false,
      meta?: any
    ) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml, fullWidth, meta }];
      });
    },
    []
  );

  const handleReset = () => {
    setMessages([]);
    setChatHistory([]);
    setRetrievedChunks([]);
    setInput("");
    setUploadedFiles([]);
    setUploadedFilesNames([]);
    setSubagentSessionId(null);
    setConversationId(null); // 👈 clear conversation id

    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.removeItem("osss_chat_messages");
        window.sessionStorage.removeItem("osss_chat_history");
        window.sessionStorage.removeItem("osss_conversation_id");
      } catch {}
    }

    let newId: string;
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) newId = crypto.randomUUID();
    else newId = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    setSessionId(newId);

    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.setItem("osss_chat_session_id", newId);
      } catch {}
    }
  };

  const handleSend = useCallback(async () => {
    if (sending) return;
    if (!sessionId) {
      console.warn("Session not ready yet");
      return;
    }

    const text = input.trim();
    if (!text && uploadedFiles.length === 0) return;

    const attachedNamesForThisTurn = [...uploadedFilesNames];

    setSending(true);
    setInput("");

    let userHtml = text ? mdToHtml(text) : "<em>(No message text)</em>";

    if (attachedNamesForThisTurn.length > 0) {
      userHtml += `
        <div style="margin-top:8px; font-size: 0.9em;">
          <strong>Attached files:</strong>
          <ul style="padding-left:16px; margin:4px 0 0 0;">
            ${attachedNamesForThisTurn.map((name) => `<li>${name}</li>`).join("")}
          </ul>
        </div>
      `;
    }

    appendMessage("user", userHtml, true);

    const historySnapshot = [...chatHistory, { role: "user" as const, content: text }];

    const hasSystem = historySnapshot.some((m) => m.role === "system");
    const baseSys = hasSystem
      ? []
      : [
          {
            role: "system" as const,
            content:
              "You are a helpful assistant for Dallas Center-Grimes Community School District (DCG) in Iowa. " +
              "When the user mentions 'DCG' or 'Dallas Center Grimes', they mean the school district, NOT the Dallas Cowboys. " +
              "Prefer information drawn from the provided DCG documents. " +
              "Respond in clear Markdown with at least 2 sentences. " +
              "Avoid including personal emails, phone numbers, or long URLs in your answer; refer to documents by title and page.",
          },
        ];

    const messagesForHistory = [...baseSys, ...historySnapshot];
    setChatHistory(messagesForHistory);

    try {
      const url = `/api/osss/api/query`;

      const body: any = {
        query: text,
        agents: [],
        execution_config: {
          parallel_execution: true,
          // ✅ NEW: allow server-side workflow longer
          timeout_seconds: 180,
          use_llm_intent: true,
          // ✅ add these:
          use_rag: true,
          top_k: 6,
        },
        correlation_id: sessionId,
        export_md: true,
      };

      // 👇 NEW: send conversation_id if we already have one
      if (conversationId) {
        body.conversation_id = conversationId;
      }

      // ✅ NEW: client-side timeout using AbortController
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), CLIENT_QUERY_TIMEOUT_MS);

      let resp: Response;
      try {
        resp = await fetch(url, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
      } finally {
        window.clearTimeout(timeoutId);
      }

      const raw = await resp.text();
      console.log("RAG raw response:", resp.status, raw);

      setLastRawResponse(raw);

      let payload: any = null;
      try {
        payload = JSON.parse(raw);
      } catch {
        appendMessage("bot", raw || "(Non-JSON response from /api/query)", false);
        setUploadedFiles([]);
        setUploadedFilesNames([]);
        setSending(false);
        return;
      }

      const wf = payload as WorkflowResponse;

      // 🔹 NEW: capture conversation_id from response and persist it
        const responseConversationId =
          wf.conversation_id ??
          wf.execution_state?.conversation_id ??
          (wf as any).conversationId; // just in case of camelCase from some older code

        if (responseConversationId && responseConversationId !== conversationId) {
          setConversationId(responseConversationId);
          if (typeof window !== "undefined") {
            try {
              window.sessionStorage.setItem("osss_conversation_id", responseConversationId);
            } catch {
              // ignore storage errors
            }
          }
        }

      // This endpoint doesn't currently return retrieved_chunks.
      setRetrievedChunks([]);
      const chunksForThisReply: RetrievedChunk[] = [];

      if (!resp.ok) {
        const msg = wf?.error_message || raw || `HTTP ${resp.status}`;
        appendMessage("bot", String(msg), false);
        setUploadedFiles([]);
        setUploadedFilesNames([]);
        setSending(false);
        return;
      }

      // Primary text to show in chat (now uses canonical final_answer)
      const reply = pickFinalAnswer(wf) || "(No agent output returned)";

      // 🔹 NEW: pull data_query canonical meta if present
      const dataQueryMeta = extractDataQueryMeta(wf.agent_outputs);

      // 🔹 Fallback: build markdown tables only if no canonical meta exists
      const dataQueryMd = dataQueryMeta ? "" : buildDataQueryMarkdown(wf.agent_outputs);

      // Pull intent/tone/etc from the query profile (new shape)
      const qp = getQueryProfile(wf);
      const returnedIntent: string | null = typeof qp?.intent === "string" ? qp.intent : null;
      const intentConfidence: number | null =
        typeof qp?.intent_confidence === "number" ? qp.intent_confidence : null;

      const intentDescription = describeIntent(returnedIntent ?? "general");
      void intentDescription;
      void intentConfidence;

      // Optional: show user-facing text (without debug) + table
      let replyForDisplay = reply.trimEnd();

      // If we have canonical data_query meta AND the reply is just that table,
      // don't render the table in the main markdown content. Let DataQueryResult
      // be the single source of truth for the table UI.
      if (
        dataQueryMeta &&
        typeof dataQueryMeta.table_markdown_compact === "string" &&
        replyForDisplay.trim() === dataQueryMeta.table_markdown_compact.trim()
      ) {
        // optional: a short label users see above the table
        replyForDisplay = "";
      }

      // Fallback: only build legacy markdown tables when we *don't* have meta
      if (dataQueryMd) {
        replyForDisplay += `\n\n---\n${dataQueryMd}`;
      }

      const replyForHistory = sanitizeForGuard(replyForDisplay);

      // build main display HTML (answer + any fallback table)
      const outHtml = mdToHtml(String(replyForDisplay));
      const sourcesHtml = showSources ? buildSourcesHtmlFromChunks(chunksForThisReply) : "";
      const finalHtml = outHtml + sourcesHtml;

      // use fullWidth if we have debug OR a data_query table (either style)
      const useFullWidth = showDebug || !!dataQueryMd || !!dataQueryMeta;

      // 1️⃣ Main bot message: answer + DataQueryResult (via meta)
      appendMessage("bot", finalHtml, true, useFullWidth, dataQueryMeta || undefined);

      // 2️⃣ Separate debug message *below* everything else
      if (showDebug) {
        const RAW_DEBUG_MAX = 50_000;
        let pretty = prettyJson(raw);
        if (pretty.length > RAW_DEBUG_MAX) {
          pretty = pretty.slice(0, RAW_DEBUG_MAX) + "\n...<truncated>...";
        }

        const debugMarkdown =
          `**/api/query raw response (HTTP ${resp.status}):**\n` +
          "```json\n" +
          pretty +
          "\n```";

        const debugHtml = mdToHtml(debugMarkdown);

        appendMessage("bot", debugHtml, true, true);
      }

      setChatHistory((prev) => [...prev, { role: "assistant", content: String(replyForHistory) }]);

    } catch (err: any) {
      // ✅ NEW: distinguish client timeout vs other errors
      if (err?.name === "AbortError") {
        appendMessage(
          "bot",
          `⏱️ Request timed out after ${(CLIENT_QUERY_TIMEOUT_MS / 1000).toFixed(
            0
          )}s waiting for /api/query.`,
          false
        );
      } else {
        appendMessage("bot", `Network error: ${String(err)}`, false);
      }
    }

    setUploadedFiles([]);
    setUploadedFilesNames([]);
    setSending(false);
  }, [
    appendMessage,
    chatHistory,
    input,
    sending,
    uploadedFiles,
    uploadedFilesNames,
    sessionId,
    showDebug,
    subagentSessionId,
    showSources,
    conversationId,
  ]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key !== "Enter") return;
    if (e.shiftKey) return; // Shift+Enter = newline

    e.preventDefault();
    void handleSend();
  };

  return (
    <div
      className="mentor-container"
      style={{ display: "flex", flexDirection: "column", height: "100vh", maxHeight: "100vh" }}
    >
      {/* Header with New Chat Button */}
      <div className="mentor-header" style={{ display: "flex", justifyContent: "space-between" }}>
        <div>General Chat — Use responsibly</div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <label
            style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "14px", cursor: "pointer" }}
          >
            <input type="checkbox" checked={showDebug} onChange={(e) => setShowDebug(e.target.checked)} />
            Debug
          </label>

          {/* NEW: Sources toggle */}
          <label
            style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "14px", cursor: "pointer" }}
          >
            <input type="checkbox" checked={showSources} onChange={(e) => setShowSources(e.target.checked)} />
            Sources
          </label>

          <button
            type="button"
            className="mentor-quick-button"
            onClick={handleReset}
            style={{
              backgroundColor: "#4CAF50",
              color: "white",
              border: "none",
              padding: "10px",
              cursor: "pointer",
              fontSize: "16px",
            }}
          >
            New Chat
          </button>
        </div>
      </div>

      {/* Uploaded files display */}
      <div className="uploaded-files">
        {uploadedFilesNames.length > 0 && (
          <div>
            <strong>Uploaded Files:</strong>
            <ul>
              {uploadedFilesNames.map((file, index) => (
                <li key={index}>{file}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="mentor-messages" style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {messages.length === 0 && <div className="mentor-empty-hint">Say hello to begin.</div>}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`mentor-msg ${m.who === "user" ? "user" : "bot"}`}
            style={
              m.fullWidth
                ? {
                    width: "100%",
                    display: "flex",
                    justifyContent: "stretch",
                  }
                : undefined
            }
          >
            <div
              className={`mentor-bubble ${m.who === "user" ? "user" : "bot"}`}
              style={
                m.fullWidth
                  ? {
                      width: "100%",
                      maxWidth: "100%",
                      alignSelf: "stretch",
                      paddingRight: "12px",
                      paddingLeft: "12px",
                      boxSizing: "border-box",
                      overflowX: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }
                  : undefined
              }
            >
              {/* ✅ Always show the main content */}
              {m.isHtml ? <div dangerouslySetInnerHTML={{ __html: m.content }} /> : m.content}

              {/* ✅ NEW: if this message has data_query meta, render the toggleable table below */}
              {m.meta &&
                (m.meta.table_markdown_compact || m.meta.table_markdown_full) && (
                  <DataQueryResult meta={m.meta} />
                )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="mentor-composer">
        <div className="textarea-container" style={{ position: "relative", width: "100%" }}>
          <input type="file" ref={fileInputRef} style={{ display: "none" }} onChange={handleFileUpload} multiple />
          <button
            type="button"
            className="file-upload-btn"
            style={{
              position: "absolute",
              left: "10px",
              top: "50%",
              transform: "translateY(-50%)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              marginRight: "10px",
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <img src={uploadIcon} alt="Upload" style={{ width: "20px", height: "20px" }} />
          </button>

          <textarea
            className="mentor-input"
            placeholder="Type your message… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            style={{ paddingLeft: "50px", width: "100%", boxSizing: "border-box" }}
          />
        </div>

        <button type="button" className="mentor-send primary" onClick={handleSend} disabled={sending}>
          {sending ? "Sending…" : "Send"}
        </button>
      </div>

      <div className="mentor-footer">Local model proxy — for experimentation and allowed use only.</div>
    </div>
  );
}
