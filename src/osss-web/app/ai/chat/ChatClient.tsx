"use client";

import React, { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "";

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
}

interface RetrievedChunk {
  score?: number;
  filename?: string;
  chunk_index?: number;
  text_preview?: string;
  image_paths?: string[] | null;
  page_index?: number | null;
  page_chunk_index?: number | null;
}

function mdToHtml(src: string): string {
  let s = src
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  s = s.replace(/```([\s\S]*?)```/g, (_m, code) => {
    return `<pre><code>${code.replace(/&/g, "&amp;")}</code></pre>`;
  });

  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  return s.replace(/\n/g, "<br/>");
}

export default function ChatClient() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  // History sent to /v1/chat/safe
  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant" | "system"; content: string }[]
  >([]);

  // NEW: debug / RAG context from backend (with images)
  const [retrievedChunks, setRetrievedChunks] = useState<RetrievedChunk[]>([]);

  const appendMessage = useCallback(
    (who: "user" | "bot", content: string, isHtml = false) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml }];
      });
    },
    []
  );

  // ✅ Reset conversation
  const handleReset = () => {
    setMessages([]);
    setChatHistory([]);
    setRetrievedChunks([]);
    setInput("");
  };

  const handleSend = useCallback(async () => {
    if (sending) return;
    const text = input.trim();
    if (!text) return;

    setSending(true);
    appendMessage("user", text, false);
    setInput("");

    // Build snapshot history including new user message
    const historySnapshot = [...chatHistory, { role: "user" as const, content: text }];

    // Ensure system prompt exists
    const hasSystem = historySnapshot.some((m) => m.role === "system");
    const baseSys = hasSystem
      ? []
      : [
          {
            role: "system" as const,
            content:
              "You are a helpful assistant. Respond in clear Markdown with at least 2 sentences.",
          },
        ];

    const messagesPayload = [...baseSys, ...historySnapshot];

    // Save updated history
    setChatHistory(messagesPayload);

    try {
      const url = `${API_BASE}/v1/chat/safe`;
      const body = {
        model: "llama3.1",
        messages: messagesPayload,
        temperature: 0.2,
        // Let backend / model decide max tokens; you can override if desired
        stream: false,
      };

      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(body),
      });

      const raw = await resp.text();

      let payload: any = null;
      try {
        payload = JSON.parse(raw);
      } catch {
        // if it isn't JSON, just show raw text
        appendMessage("bot", raw || "(Non-JSON response from /v1/chat/safe)", false);
        setSending(false);
        return;
      }

      // NEW: pick up retrieved_chunks (if this is a RAG-style response)
      const maybeChunks = payload?.retrieved_chunks;
      if (Array.isArray(maybeChunks)) {
        setRetrievedChunks(maybeChunks as RetrievedChunk[]);
      } else {
        setRetrievedChunks([]);
      }

      // Most /v1/chat/safe responses wrap the OpenAI-style object in `answer`
      const core = payload?.answer ?? payload;

      if (!resp.ok) {
        const msg =
          core?.detail?.reason ||
          core?.detail ||
          raw ||
          `HTTP ${resp.status}`;
        appendMessage("bot", String(msg), false);
        setSending(false);
        return;
      }

      let reply: string =
        core?.message?.content ??
        core?.choices?.[0]?.message?.content ??
        core?.choices?.[0]?.text ??
        (typeof core === "string" ? core : raw);

      if (!reply?.trim()) {
        reply = "(Empty reply from /v1/chat/safe)";
      }

      const outHtml = mdToHtml(String(reply));
      appendMessage("bot", outHtml, true);

      // Add assistant turn to history
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: String(reply) },
      ]);
    } catch (err: any) {
      appendMessage("bot", `Network error: ${String(err)}`, false);
    }

    setSending(false);
  }, [appendMessage, chatHistory, input, sending]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="mentor-container">
      {/* Header */}
      <div className="mentor-header">
        <div>General Chat — Use responsibly</div>
        <div className="mentor-header-right">
          <code className="inline-code">LLM (OpenAI-compatible)</code>
        </div>
      </div>

      {/* Toolbar: RESET */}
      <div className="mentor-toolbar">
        <button
          type="button"
          className="mentor-quick-button"
          onClick={handleReset}
        >
          🔄 New chat
        </button>
      </div>

      {/* Messages */}
      <div className="mentor-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="mentor-empty-hint">Say hello to begin.</div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`mentor-msg ${m.who === "user" ? "user" : "bot"}`}
          >
            <div className={`mentor-bubble ${m.who === "user" ? "user" : "bot"}`}>
              {m.isHtml ? (
                <div dangerouslySetInnerHTML={{ __html: m.content }} />
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Retrieved RAG context (with images) */}
      {retrievedChunks.length > 0 && (
        <div className="rag-debug-panel">
          <div className="rag-debug-title">Retrieved context</div>
          <div className="rag-debug-list">
            {retrievedChunks.map((c, idx) => {
              const key =
                `${c.filename ?? "chunk"}-${c.chunk_index ?? idx}-${c.page_index ?? "p"}`;
              return (
                <div className="rag-chunk-card" key={key}>
                  <div className="rag-chunk-header">
                    <span className="rag-chunk-filename">
                      {c.filename ?? "Unknown file"}
                    </span>
                    {typeof c.score === "number" && (
                      <span className="rag-chunk-score">
                        score: {c.score.toFixed(3)}
                      </span>
                    )}
                  </div>

                  {/* Images */}
                  {c.image_paths && c.image_paths.length > 0 && (
                    <div className="rag-chunk-images">
                      {c.image_paths.map((p, i) => {
                        if (!p) return null;
                        // If backend serves images under /rag-images, prefix here.
                        // If your API exposes full URLs already, you can just use `p`.
                        const src = p.startsWith("http")
                          ? p
                          : `/rag-images/${p}`;
                        return (
                          <img
                            key={`${key}-img-${i}`}
                            src={src}
                            alt={c.text_preview?.slice(0, 80) || "RAG image"}
                            className="rag-image"
                          />
                        );
                      })}
                    </div>
                  )}

                  {/* Text preview */}
                  {c.text_preview && (
                    <div className="rag-chunk-text">
                      {c.text_preview}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Composer */}
      <div className="mentor-composer">
        <textarea
          className="mentor-input"
          placeholder="Type your message… (Ctrl/Cmd+Enter to send)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />

        <button
          type="button"
          className="mentor-send primary"
          onClick={() => void handleSend()}
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
