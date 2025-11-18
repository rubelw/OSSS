"use client";

import React, {
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "/api/osss";

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
  imagePaths?: string[];
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

function mdToHtml(src: string): string {
  let s = src
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks
  s = s.replace(/```([\s\S]*?)```/g, (_m, code) => {
    return `<pre><code>${code.replace(/&/g, "&amp;")}</code></pre>`;
  });

  // Inline code
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Markdown links in model output (if any) – will only be things the model emitted,
  // since we stripped our own before putting them in history.
  s = s.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
  );

  // Bold
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // Newlines
  return s.replace(/\n/g, "<br/>");
}

export default function ChatClient() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant" | "system"; content: string }[]
  >([]);

  const [retrievedChunks, setRetrievedChunks] = useState<RetrievedChunk[]>([]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  const appendMessage = useCallback(
    (
      who: "user" | "bot",
      content: string,
      isHtml = false,
      imagePaths?: string[]
    ) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml, imagePaths }];
      });
    },
    []
  );

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

    const messagesPayload = [...baseSys, ...historySnapshot];

    setChatHistory(messagesPayload);

    try {
      const url = `${API_BASE}/v1/chat/safe`;
      const body = {
        model: "llama3.1",
        messages: messagesPayload,
        temperature: 0.2,
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
        appendMessage("bot", raw || "(Non-JSON response from /v1/chat/safe)", false);
        setSending(false);
        return;
      }

      // ---- 1) retrieved_chunks -> store for UI ONLY ------------------------
      const maybeChunks = payload?.retrieved_chunks;
      let chunkImagePaths: string[] = [];

      if (Array.isArray(maybeChunks)) {
        const chunks = maybeChunks as RetrievedChunk[];
        setRetrievedChunks(chunks);

        // Collect image paths for thumbnails (bot bubble “Related images”)
        chunkImagePaths = chunks
          .flatMap((c) => c.image_paths ?? [])
          .filter((p): p is string => !!p);
      } else {
        setRetrievedChunks([]);
      }

      console.log("SAFE raw payload:", payload);
      console.log("retrieved_chunks (if any):", payload?.retrieved_chunks);

      const replyImagePaths: string[] = [...chunkImagePaths];

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

      // ---- 2) Text reply (NO context summary appended) ---------------------
      let reply: string =
        core?.message?.content ??
        core?.choices?.[0]?.message?.content ??
        core?.choices?.[0]?.text ??
        (typeof core === "string" ? core : raw);

      if (!reply?.trim()) {
        reply = "(Empty reply from /v1/chat/safe)";
      }

      // Strip PII / URLs / markdown links from what goes back into history
      reply = sanitizeForGuard(reply);

      const outHtml = mdToHtml(String(reply));

      appendMessage(
        "bot",
        outHtml,
        true,
        replyImagePaths.length ? replyImagePaths : undefined
      );

      // Store sanitized reply in history (no URLs / link-like patterns)
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

  // All image URLs for the “Related photos” strip
  const allImageUrls: string[] = Array.from(
    new Set(
      (retrievedChunks || [])
        .flatMap((c) => c.image_paths ?? [])
        .filter((p): p is string => !!p)
        .map((p) => p)
    )
  );

  return (
    <div
      className="mentor-container"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxHeight: "100vh",
      }}
    >
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
      <div
        className="mentor-messages"
        aria-live="polite"
        style={{
          flex: 1,
          overflowY: "auto",
          minHeight: 0,
        }}
      >
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

              {/* Retrieved context panel INSIDE the bot message bubble */}
                {m.who === "bot" && retrievedChunks.length > 0 && (
                  <div className="rag-context-panel" style={{ marginTop: "12px" }}>
                    <div
                      className="rag-context-title"
                      style={{ fontWeight: "bold", marginBottom: "6px" }}
                    >
                      Retrieved context
                    </div>
                    <ul className="rag-context-list" style={{ paddingLeft: "16px" }}>
                      {retrievedChunks.map((c, idx) => {
                        const filename = c.filename ?? "Unknown file";

                        // 1) Try image snapshot href first
                        const rawImage = c.image_paths?.[0];
                        let linkPath: string | undefined;

                        if (rawImage) {
                          // http://localhost:8081/rag-images/... -> /rag-images/...
                          const relative = rawImage.replace(/^https?:\/\/[^/]+/, "");
                          linkPath = encodeURI(relative);
                        } else if (filename !== "Unknown file") {
                          // 2) Fallback: link to the original PDF by filename
                          //    Adjust this route prefix to match your FastAPI PDF endpoint.
                          const safeName = encodeURIComponent(filename);
                          linkPath = `/rag-pdfs/main/${safeName}`;
                        }

                        const metaParts: string[] = [];
                        if (typeof c.page_index === "number") {
                          metaParts.push(`page ${c.page_index + 1}`);
                        }
                        if (typeof c.score === "number") {
                          metaParts.push(`score ${c.score.toFixed(3)}`);
                        }
                        const metaInfo = metaParts.length
                          ? ` – ${metaParts.join(" – ")}`
                          : "";

                        const rawPreview = c.text_preview ?? "";
                        const cleanedPreview = rawPreview.replace(/\s+/g, " ").trim();
                        const shortPreview =
                          cleanedPreview.length > 200
                            ? cleanedPreview.slice(0, 197) + "..."
                            : cleanedPreview;

                        // Visible text as a Markdown-style link string
                        const markdownLink =
                          linkPath && filename !== "Unknown file"
                            ? `[${filename}](${linkPath})`
                            : filename;

                        return (
                          <li
                            key={idx}
                            className="rag-context-item"
                            style={{ marginBottom: "4px" }}
                          >
                            {linkPath ? (
                              <a href={linkPath} target="_blank" rel="noreferrer">
                                {markdownLink}
                              </a>
                            ) : (
                              <span>{markdownLink}</span>
                            )}
                            {metaInfo && <span>{metaInfo}</span>}
                            {shortPreview && (
                              <span className="rag-context-preview">
                                {": "}
                                {shortPreview}
                              </span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Related photos (thumbnails from retrievedChunks) */}
      {allImageUrls.length > 0 && (
        <div className="rag-photos-panel">
          <div className="rag-photos-title">Related photos</div>
          <div className="rag-photos-grid">
            {allImageUrls.map((url, idx) => (
              <div key={`${url}-${idx}`} className="rag-photo-wrapper">
                <img
                  src={url}
                  alt="Related document image"
                  className="rag-photo-img"
                />
              </div>
            ))}
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
