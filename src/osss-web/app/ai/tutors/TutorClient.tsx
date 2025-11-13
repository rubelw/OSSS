"use client";

import React, { useState, useCallback, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "";
const TUTOR_API_BASE = API_BASE ? `${API_BASE}/tutor` : "/tutor";

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
}

interface TutorInfo {
  tutor_id: string;
  display_name?: string;
}

function mdToHtml(src: string): string {
  let s = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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

  const [tutors, setTutors] = useState<TutorInfo[]>([]);
  const [selectedTutorId, setSelectedTutorId] = useState<string>("");

  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);

  // Load /tutor/tutors
  useEffect(() => {
    const loadTutors = async () => {
      try {
        const resp = await fetch(`${TUTOR_API_BASE}/tutors`, {
          headers: { Accept: "application/json" },
        });

        if (!resp.ok) return;

        const data = await resp.json();
        if (!Array.isArray(data)) return;

        const mapped: TutorInfo[] = data.map((t: any) => ({
          tutor_id: t.tutor_id,
          display_name: t.display_name,
        }));

        setTutors(mapped);

        // Prefer math8 if present
        const math8 = mapped.find(
          (t) => (t.tutor_id || "").toLowerCase() === "math8"
        );
        setSelectedTutorId(math8 ? math8.tutor_id : mapped[0]?.tutor_id ?? "");
      } catch (err) {
        console.error("Error loading tutors", err);
      }
    };

    void loadTutors();
  }, []);

  const appendMessage = useCallback(
    (who: "user" | "bot", content: string, isHtml = false) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml }];
      });
    },
    []
  );

  const handleSend = useCallback(async () => {
    if (sending) return;
    const text = input.trim();
    if (!text) return;

    if (!selectedTutorId) {
      appendMessage("bot", "No tutor is selected.", false);
      return;
    }

    setSending(true);
    appendMessage("user", text, false);
    setInput("");

    try {
      const url = `${TUTOR_API_BASE}/tutors/${encodeURIComponent(
        selectedTutorId
      )}/chat`;

      const historySnapshot = [
        ...chatHistory,
        { role: "user" as const, content: text },
      ];

      const body = {
        message: text,
        history: historySnapshot,
        use_rag: false,
        max_tokens: 256,
      };

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

      // --- Tutor response parsing ---
      let replyText = "";
      if (payload && typeof payload === "object" && "answer" in payload) {
        replyText = payload.answer || "";

        if (Array.isArray(payload.sources) && payload.sources.length) {
          replyText +=
            "\n\nSources:\n" +
            payload.sources
              .map(
                (s: any, i: number) =>
                  `  ${i + 1}. ${
                    s.source || s.file || "doc"
                  } (p${s.page ?? "?"})`
              )
              .join("\n");
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
    } catch (err) {
      appendMessage("bot", `Network error: ${String(err)}`, false);
    }

    setSending(false);
  }, [appendMessage, chatHistory, input, sending, selectedTutorId]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  };

  const activeTutor = tutors.find((t) => t.tutor_id === selectedTutorId);
  const headerTitle =
    activeTutor?.display_name || (selectedTutorId ? `Tutor: ${selectedTutorId}` : "Tutor");

  return (
    <div className="mentor-container">
      {/* Header */}
      <div className="mentor-header">
        <div>{headerTitle} — Use responsibly</div>
        <div className="mentor-header-right">
          <code className="inline-code">Tutor (FastAPI)</code>
        </div>
      </div>

      {/* Toolbar: only the dropdown now */}
      <div className="mentor-toolbar">
        <label className="mentor-label">
          Tutor
          <select
            className="mentor-select"
            value={selectedTutorId}
            onChange={(e) => {
              setSelectedTutorId(e.target.value);
              setMessages([]);
              setChatHistory([]);
              setInput("");
            }}
          >
            {tutors.length === 0 && (
              <option value="">(no tutors found)</option>
            )}
            {tutors.map((t) => (
              <option key={t.tutor_id} value={t.tutor_id}>
                {t.display_name || t.tutor_id}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Messages */}
      <div className="mentor-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="mentor-empty-hint">
            Select a tutor, then ask a question (e.g. Math 8 or Geography 8 topics).
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`mentor-msg ${m.who === "user" ? "user" : "bot"}`}
          >
            <div
              className={`mentor-bubble ${m.who === "user" ? "user" : "bot"}`}
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
          placeholder="Type your question… (Ctrl/Cmd+Enter to send)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          className="mentor-send primary"
          onClick={() => void handleSend()}
          disabled={sending || !selectedTutorId}
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
