"use client";

import React, { useState, useCallback, useEffect } from "react";

// Base for chat-safe (Next.js route)
const CHAT_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "";

// Base for OSSS API / FastAPI (mentors)
const MENTOR_API_BASE =
  process.env.NEXT_PUBLIC_OSSS_API_BASE ??
  process.env.NEXT_PUBLIC_CHAT_API_BASE ??
  "";

console.log("[MentorClient] CHAT_BASE =", CHAT_BASE);
console.log("[MentorClient] MENTOR_API_BASE =", MENTOR_API_BASE);

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
}

interface Mentor {
  id: string;
  intent: string;
  label: string;
}

const STATIC_MENTORS: Mentor[] = [
  { id: "career", intent: "start_career_mentor", label: "Career Mentor" },
  { id: "geography", intent: "start_geography_mentor", label: "Geography Mentor" },
];

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
  const [sender, setSender] = useState("user_" + Date.now());

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const [mentors, setMentors] = useState<Mentor[]>([]);
  const [selectedMentor, setSelectedMentor] = useState<string>("");
  const [mentorsLoading, setMentorsLoading] = useState(false);
  const [mentorsError, setMentorsError] = useState<string | null>(null);

  useEffect(() => {
    const loadMentors = async () => {
      try {
        setMentorsLoading(true);
        setMentorsError(null);

        if (!MENTOR_API_BASE) {
          console.warn(
            "[MentorClient] MENTOR_API_BASE is empty; using static mentors only."
          );
          setMentors(STATIC_MENTORS);
          return;
        }

        const url = `${MENTOR_API_BASE.replace(/\/$/, "")}/rasa/mentors`;
        console.log("[MentorClient] Fetching mentors from", url);

        const resp = await fetch(url, {
          method: "GET",
          headers: { Accept: "application/json" },
        });

        const text = await resp.text();
        if (!resp.ok) {
          throw new Error(
            `HTTP ${resp.status} from /rasa/mentors: ${text || "(empty body)"}`
          );
        }

        const data = (text ? JSON.parse(text) : []) as Mentor[];
        if (!Array.isArray(data) || data.length === 0) {
          console.warn(
            "[MentorClient] /rasa/mentors returned empty or invalid payload; using static mentors fallback."
          );
          setMentors(STATIC_MENTORS);
        } else {
          setMentors(data);
        }
      } catch (err: any) {
        const msg = String(err);
        console.error("[MentorClient] Failed to load mentors:", err);
        setMentorsError(msg);
        // still give the user something usable
        setMentors(STATIC_MENTORS);
      } finally {
        setMentorsLoading(false);
      }
    };

    void loadMentors();
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

  const handleSelectMentor: React.ChangeEventHandler<HTMLSelectElement> = (e) => {
    const value = e.target.value;
    setSelectedMentor(value);

    if (!value) return;

    setMessages([]);
    setSender("user_" + Date.now());
    setInput(`start ${value} mentor`);
  };

  const handleSend = useCallback(
    async () => {
      if (sending) return;
      const text = input.trim();
      if (!text) return;

      setSending(true);
      appendMessage("user", text, false);
      setInput("");

      try {
        const base = CHAT_BASE || "";
        const url = `${base.replace(/\/$/, "")}/rasa/chat-safe`;
        console.log("[MentorClient] Sending chat to", url);

        const body = { sender, message: text };

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
          // non-JSON response
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
    },
    [appendMessage, input, sending, sender]
  );

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="mentor-container">
      <div className="mentor-header">
        <div>Mentors — Use responsibly</div>
        <div className="mentor-header-right">
          <code className="inline-code">Rasa Chat</code>
        </div>
      </div>

      {/* Toolbar: mentor selector */}
      <div className="mentor-toolbar">
        <label className="mentor-label">
          Mentor:
          <select
            className="mentor-select"
            value={selectedMentor}
            onChange={handleSelectMentor}
            disabled={mentorsLoading || mentors.length === 0}
          >
            <option value="">Select a mentor…</option>
            {mentors.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        {mentorsLoading && (
          <span className="mentor-status-text">Loading mentors…</span>
        )}
        {/* Only show error if we *also* have no mentors */}
        {mentorsError && mentors.length === 0 && (
          <span className="mentor-status-text error">
            Failed to load mentors: {mentorsError}
          </span>
        )}
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
