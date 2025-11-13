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

export default function MentorClient() {
  // 🔥 SENDER IS NOW STATE — NEW SESSION EACH RESET
  const [sender, setSender] = useState("user_" + Date.now());

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const appendMessage = useCallback(
    (who: "user" | "bot", content: string, isHtml = false) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml }];
      });
    },
    []
  );

  // ✅ RESET + NEW SENDER ID
  const handleQuickCareer = () => {
    setMessages([]);          // clear chat UI
    setInput("start career mentor"); // pre-fill
    setSender("user_" + Date.now()); // 🔥 new conversation session
  };

  const handleSend = useCallback(async () => {
    if (sending) return;
    const text = input.trim();
    if (!text) return;

    setSending(true);
    appendMessage("user", text, false);
    setInput("");

    try {
      const url = `${API_BASE}/rasa/chat-safe`;
      const body = { sender, message: text }; // 🔥 NEW sender each reset

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

      let combined = "";
      if (Array.isArray(payload)) {
        combined = payload
          .map((m: any) => m.text || m.image || m.custom || "")
          .filter(Boolean)
          .join("\n\n");
      } else {
        combined = typeof payload === "string" ? payload : raw;
      }

      const out = mdToHtml(combined || "");
      appendMessage("bot", out || "<em>(empty)</em>", true);
    } catch (err: any) {
      appendMessage("bot", `Network error: ${String(err)}`, false);
    }

    setSending(false);
  }, [appendMessage, input, sending, sender]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="mentor-container">
      <div className="mentor-header">
        <div>Career Mentor — Use responsibly</div>
        <div className="mentor-header-right">
          <code className="inline-code">Rasa Chat</code>
        </div>
      </div>

      {/* Toolbar */}
      <div className="mentor-toolbar">
        <button
          type="button"
          className="mentor-quick-button"
          onClick={handleQuickCareer}
        >
          🎓 Career Mentor
        </button>
      </div>

      {/* Message list */}
      <div className="mentor-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="mentor-empty-hint">
            Conversation will appear here as you chat.
          </div>
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
