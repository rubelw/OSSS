// simple proxy + static server with optional Markdown rendering
// Usage: NODE_ENV=production node server.js
const express = require("express");
const fetch = require("node-fetch"); // v2-compatible API in node:18 via node-fetch v2
const path = require("path");
const { marked } = require("marked"); // <-- markdown renderer

const PORT = process.env.PORT || 3000;
const TARGET_HOST =
  process.env.TARGET_HOST || "http://host.docker.internal:8081"; // Docker for Mac/Linux: host.docker.internal
const app = express();

app.use(express.static(path.join(__dirname, "public")));
app.use(express.json());

// Helpers
function wantsHTML(req) {
  return (
    (req.query.format && req.query.format.toLowerCase() === "html") ||
    (req.headers.accept || "").toLowerCase().includes("text/html")
  );
}

function extractTextFromUpstream(json) {
  // Try common OpenAI-compatible shapes first
  if (json?.choices?.[0]?.message?.content) return json.choices[0].message.content;
  if (json?.choices?.[0]?.text) return json.choices[0].text;
  if (json?.result?.[0]?.content) return json.result[0].content;
  // Fallback: stringify
  return typeof json === "string" ? json : JSON.stringify(json);
}

// Single proxy worker used by both endpoints
async function handleChatProxy(req, res, { forceHtml = false } = {}) {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }
    const body = req.body;
    if (!body || !Array.isArray(body.messages) || body.messages.length === 0) {
      return res.status(400).json({ error: "Request must include messages array" });
    }

    const upstream = `${TARGET_HOST}/v1/chat/completions`;
    const upstreamResp = await fetch(upstream, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: req.get("Authorization") || "",
      },
      body: JSON.stringify(body),
    });

    const raw = await upstreamResp.text();
    const wantHtml = forceHtml || wantsHTML(req);

    if (wantHtml) {
      let json;
      try {
        json = JSON.parse(raw);
      } catch {
        const html = marked.parse(raw || "");
        return res.status(upstreamResp.status).type("html").send(html);
      }
      const text = extractTextFromUpstream(json);
      const html = marked.parse(text || "");
      return res.status(upstreamResp.status).type("html").send(html);
    }

    // Otherwise, pass through JSON (or text if not JSON)
    res.status(upstreamResp.status);
    try {
      res.json(JSON.parse(raw));
    } catch {
      res.type("text").send(raw);
    }
  } catch (err) {
    console.error("Proxy error:", err);
    res.status(500).json({ error: "Proxy error", detail: String(err) });
  }
}

// --- Routes ---
// JSON by default
app.post("/v1/chat/completions", (req, res) =>
  handleChatProxy(req, res, { forceHtml: false })
);

// Always HTML (no self-dispatch recursion)
app.post("/chat-html", (req, res) =>
  handleChatProxy(req, res, { forceHtml: true })
);

// Simple health
app.get("/healthz", (req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`Chat UI server listening on port ${PORT}`);
  console.log(`Proxying model requests to ${TARGET_HOST}/v1/chat/completions`);
  console.log(`Tip: add "?format=html" or send "Accept: text/html" to get rendered HTML.`);
});
