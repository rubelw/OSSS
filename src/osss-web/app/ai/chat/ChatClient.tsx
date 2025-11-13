"use client";

import React, { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "";

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

export default function ChatClient() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  // History sent to /v1/chat/safe
  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant" | "system"; content: string }[]
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

  const handleQuickGeneral = () => {
    setInput("Hello!");
  };

  // ✅ NEW: Reset conversation
  const handleReset = () => {
    setMessages([]);
    setChatHistory([]);
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
        max_tokens: 256,
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
      } catch {}

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

      let reply: string =
        payload?.message?.content ??
        payload?.choices?.[0]?.message?.content ??
        payload?.choices?.[0]?.text ??
        (typeof payload === "string" ? payload : raw);

      if (!reply?.trim()) reply = "(Empty reply from /v1/chat/safe)";

      const outHtml = mdToHtml(String(reply));
      appendMessage("bot", outHtml, true);

      // Add assistant turn to history
      setChatHistory((prev) => [...prev, { role: "assistant", content: String(reply) }]);
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

      {/* Toolbar: quick example + RESET */}
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
