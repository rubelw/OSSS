"use client";

import React, { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "";
const TUTOR_API_BASE = API_BASE ? `${API_BASE}/tutor` : "/tutor";
const MATH_TUTOR_ID = "math8";

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
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

export default function TutorClient() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  // History we send to the tutor backend
  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);

  const appendMessage = useCallback(
    (who: "user" | "bot", content: string, isHtml = false) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml }];
      });
    },
    []
  );

  // ✅ RESET + EXAMPLE
  const handleQuickMath = () => {
    setMessages([]); // clear UI chat bubbles
    setChatHistory([]); // clear history sent to backend
    setInput("How do I add 1 + 1?"); // pre-fill starter question
  };

  const handleSend = useCallback(async () => {
    if (sending) return;
    const text = input.trim();
    if (!text) return;

    setSending(true);
    appendMessage("user", text, false);
    setInput("");

    try {
      const url = `${TUTOR_API_BASE}/tutors/${encodeURIComponent(
        MATH_TUTOR_ID
      )}/chat`;

      // ✅ Use a snapshot that includes this new user turn
      const historySnapshot = [
        ...chatHistory,
        { role: "user" as const, content: text },
      ];

      const body = {
        message: text,
        history: historySnapshot, // FastAPI tutor expects role/content pairs
        use_rag: false,
        max_tokens: 256,
      };

      // Save updated history for future turns
      setChatHistory(historySnapshot);

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
        /* ignore */
      }

      if (!resp.ok) {
        const msg =
          payload?.detail?.reason ||
          payload?.detail ||
          raw ||
          `HTTP ${resp.status}`;
        appendMessage("bot", String(msg), false);
        setSending(false);
        return;
      }

      // Tutor-style response: { answer, sources? }
      let replyText = "";
      if (payload && typeof payload === "object" && "answer" in payload) {
        replyText = payload.answer || "";

        if (Array.isArray(payload.sources) && payload.sources.length) {
          const sourcesText =
            "\n\nSources:\n" +
            payload.sources
              .map(
                (s: any, i: number) =>
                  `  ${i + 1}. ${
                    s.source || s.file || "doc"
                  } (p${s.page ?? "?"})`
              )
              .join("\n");
          replyText += sourcesText;
        }
      } else {
        replyText =
          typeof payload === "string"
            ? payload
            : raw || JSON.stringify(payload ?? {}, null, 2);
      }

      const safeReply = replyText || "(empty tutor response)";
      const out = mdToHtml(safeReply);
      appendMessage("bot", out, true);

      // Add assistant turn to history (only the plain answer part if present)
      const plainAnswer =
        payload && typeof payload === "object" && "answer" in payload
          ? payload.answer || ""
          : safeReply;

      if (plainAnswer) {
        setChatHistory((prev) => [
          ...prev,
          { role: "assistant", content: plainAnswer },
        ]);
      }
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
        <div>Math 8 Tutor — Use responsibly</div>
        <div className="mentor-header-right">
          <code className="inline-code">Tutor (FastAPI)</code>
        </div>
      </div>

      {/* Toolbar: quick example + reset */}
      <div className="mentor-toolbar">
        <button
          type="button"
          className="mentor-quick-button"
          onClick={handleQuickMath}
        >
          📐 Math 8 example
        </button>
      </div>

      {/* Messages area */}
      <div className="mentor-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="mentor-empty-hint">
            Ask the Math 8 tutor a question (for example: “How do I add 1 + 1?”).
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`mentor-msg ${m.who === "user" ? "user" : "bot"}`}
          >
            <div
              className={`mentor-bubble ${
                m.who === "user" ? "user" : "bot"
              }`}
            >
              {m.isHtml ? (
                <div dangerouslySetInnerHTML={{ __html: m.content }} />
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Composer */}
      <div className="mentor-composer">
        <textarea
          className="mentor-input"
          placeholder="Type your math question… (Ctrl/Cmd+Enter to send)"
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
