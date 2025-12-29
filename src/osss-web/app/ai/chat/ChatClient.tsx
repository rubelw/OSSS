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
  fullWidth?: boolean;
  meta?: any; // no longer used for data_query tables, but kept for future use
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

  // top-level conversation id (matches your raw JSON)
  conversation_id?: string | null;

  execution_state?: {
    conversation_id?: string | null;
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
  // 1) Prefer canonical final_answer from execution_state / structured_outputs
  const es: any = wf.execution_state || {};
  const fromExecState =
    es.final?.final_answer ??
    es.structured_outputs?.final?.final_answer ??
    wf.workflow_result?.structured_outputs?.final?.final_answer;

  if (typeof fromExecState === "string" && fromExecState.trim()) {
    return fromExecState;
  }

  // 2) If top-level answer exists and is not just an LLMResponse(...) debug wrapper, use it
  if (
    typeof wf.answer === "string" &&
    wf.answer.trim() &&
    !looksLikeLLMResponseWrapper(wf.answer)
  ) {
    return wf.answer;
  }

  // 3) Last resort: old behavior (look at agent_outputs.final / refiner / first string)
  return pickPrimaryText(wf.agent_outputs);
}

function pickPrimaryText(agentOutputs: Record<string, any> | undefined): string {
  if (!agentOutputs) return "";

  const finalOutput = agentOutputs.final;
  if (typeof finalOutput === "string" && finalOutput.trim()) return finalOutput;

  const refinerOutput = agentOutputs.refiner;
  if (typeof refinerOutput === "string" && refinerOutput.trim()) return refinerOutput;

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
 * Small Markdown → HTML helper:
 * - code blocks
 * - inline code
 * - links
 * - bold
 * - bullet lists
 * - tables
 */
function mdToHtml(src: string): string {
  // Escape HTML
  let s = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Normalize inline bullets into real lines
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

  // Line-based processing: lists + tables
  const lines = s.split(/\n/);
  let inList = false;
  const out: string[] = [];

  const isTableSeparator = (line: string): boolean => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("|")) return false;
    return /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(trimmed);
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    const trimmed = line.trim();
    const looksLikeTableRow = trimmed.startsWith("|") && trimmed.includes("|");

    // Header + separator = start of table
    if (looksLikeTableRow && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }

      // Header row
      const headerCells = trimmed
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((c) => c.trim());

      out.push('<table class="md-table"><thead><tr>');
      headerCells.forEach((cell) => out.push(`<th>${cell}</th>`));
      out.push("</tr></thead><tbody>");

      // Skip separator
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

    // Bullet lists
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
    const sourcePath: string | undefined =
      (c as any).pdf_index_path || (c as any).source || c.filename || undefined;

    if (!sourcePath) continue;

    const safeSegments = sourcePath.split("/").map((seg) => encodeURIComponent(seg));
    const href = `/rag-pdfs/main/${safeSegments.join("/")}`;

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
 * Map the raw intent label to a more descriptive explanation.
 * (kept for future use; not shown in UI)
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
    default:
      return "general information / mixed audience";
  }
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

  // toggle "Sources" block on/off
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

  // conversation id state, persisted in sessionStorage
  const [conversationId, setConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const stored = window.sessionStorage.getItem("osss_conversation_id");
      return stored || null;
    } catch {
      return null;
    }
  });

  // subagent session id (e.g. registration workflow)
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

  // On mount: restore messages & history & conversationId
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
        if (typeof crypto !== "undefined" && "randomUUID" in crypto)
          initial = crypto.randomUUID();
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

  const appendMessage = useCallback(
    (who: "user" | "bot", content: string, isHtml = false, fullWidth = false, meta?: any) => {
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
    setConversationId(null);

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
          timeout_seconds: 180,
          use_llm_intent: true,
          use_rag: true,
          top_k: 6,
        },
        correlation_id: sessionId,
        export_md: true,
      };

      if (conversationId) {
        body.conversation_id = conversationId;
      }

      // client-side timeout using AbortController
      const controller = new AbortController();
      const timeoutId = window.setTimeout(
        () => controller.abort(),
        CLIENT_QUERY_TIMEOUT_MS
      );

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

      // --- conversation_id handling ---
      // If the API explicitly returns `"conversation_id": null` at the top level,
      // treat that as a signal to CLEAR the local conversation state.
      const hasTopLevelConvKey = Object.prototype.hasOwnProperty.call(
        wf,
        "conversation_id"
      );
      const topLevelConv = wf.conversation_id;
      const execConv =
        wf.execution_state &&
        Object.prototype.hasOwnProperty.call(wf.execution_state, "conversation_id")
          ? wf.execution_state.conversation_id
          : undefined;
      const camelConv = (wf as any).conversationId as string | null | undefined;

      if (hasTopLevelConvKey && topLevelConv === null) {
        // explicit reset from server (e.g., cancel / end-of-conversation)
        if (conversationId !== null) {
          setConversationId(null);
          if (typeof window !== "undefined") {
            try {
              window.sessionStorage.removeItem("osss_conversation_id");
            } catch {
              // ignore storage errors
            }
          }
        }
      } else {
        const responseConversationId = topLevelConv ?? execConv ?? camelConv;
        if (responseConversationId && responseConversationId !== conversationId) {
          setConversationId(responseConversationId);
          if (typeof window !== "undefined") {
            try {
              window.sessionStorage.setItem(
                "osss_conversation_id",
                responseConversationId
              );
            } catch {
              // ignore storage errors
            }
          }
        }
      }
      // --- end conversation_id handling ---

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

      // Primary text to show in chat (canonical final_answer or fallback)
      const reply = pickFinalAnswer(wf) || "(No agent output returned)";
      const replyForDisplay = reply.trimEnd();

      // Intent (not shown, but kept if you want for logging)
      const qp = getQueryProfile(wf);
      const returnedIntent: string | null = typeof qp?.intent === "string" ? qp.intent : null;
      const intentConfidence: number | null =
        typeof qp?.intent_confidence === "number" ? qp.intent_confidence : null;
      const intentDescription = describeIntent(returnedIntent ?? "general");
      void intentDescription;
      void intentConfidence;

      const replyForHistory = sanitizeForGuard(replyForDisplay);

      // build main display HTML (answer only) + sources block
      const outHtml = mdToHtml(String(replyForDisplay));
      const sourcesHtml = showSources ? buildSourcesHtmlFromChunks(chunksForThisReply) : "";
      const finalHtml = outHtml + sourcesHtml;

      // use fullWidth only if debug is on (no data_query tables anymore)
      const useFullWidth = showDebug;

      appendMessage("bot", finalHtml, true, useFullWidth);

      // Optional debug message
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

      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: String(replyForHistory) },
      ]);
    } catch (err: any) {
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
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "14px",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={showDebug}
              onChange={(e) => setShowDebug(e.target.checked)}
            />
            Debug
          </label>

          {/* Sources toggle */}
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "14px",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={showSources}
              onChange={(e) => setShowSources(e.target.checked)}
            />
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
        {messages.length === 0 && (
          <div className="mentor-empty-hint">Say hello to begin.</div>
        )}
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
              {m.isHtml ? (
                <div dangerouslySetInnerHTML={{ __html: m.content }} />
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="mentor-composer">
        <div className="textarea-container" style={{ position: "relative", width: "100%" }}>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            onChange={handleFileUpload}
            multiple
          />
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

        <button
          type="button"
          className="mentor-send primary"
          onClick={handleSend}
          disabled={sending}
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>

      <div className="mentor-footer">
        Local model proxy — for experimentation and allowed use only.
      </div>
    </div>
  );
}
