// simple proxy + static server with optional Markdown rendering
// Usage: NODE_ENV=production node server.js
const express = require("express");
const fetch = require("node-fetch"); // v2-compatible API in node:18 via node-fetch v2
const path = require("path");
const { marked } = require("marked"); // <-- markdown renderer

const PORT = process.env.PORT || 3000;

// LLM proxy target (OpenAI-compatible)
const TARGET_HOST =
  process.env.TARGET_HOST || "http://host.docker.internal:8081";

// Rasa service
const RASA_URL =
  process.env.RASA_URL || "http://rasa-mentor:5005";

// Tutor (FastAPI) base — default builds off TARGET_HOST
// Example overrides:
//   TUTOR_HOST=http://host.containers.internal:8081/tutor
//   TUTOR_HOST=http://app:8081/tutor   (when sharing a compose network)
const TUTOR_HOST = (process.env.TUTOR_HOST || `${TARGET_HOST}/tutor`).replace(/\/+$/,"");

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

// ---------- OpenAI-compatible chat proxy ----------
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

// --- Routes (LLM) ---
// JSON by default
app.post("/v1/chat/completions", (req, res) =>
  handleChatProxy(req, res, { forceHtml: false })
);
// Always HTML
app.post("/chat-html", (req, res) =>
  handleChatProxy(req, res, { forceHtml: true })
);

// ---------- Rasa proxies ----------

// Chat with Rasa (dialogue via REST channel)
// Body: { sender: "user-id", message: "hi there" }
app.post("/rasa/chat", async (req, res) => {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }
    const { sender, message, metadata } = req.body || {};
    if (!message) return res.status(400).json({ error: "Body must include 'message'." });

    // Default sender if omitted
    const payload = {
      sender: sender || "user",
      message,
      ...(metadata ? { metadata } : {}),
    };

    const upstream = `${RASA_URL}/webhooks/rest/webhook`;
    const upstreamResp = await fetch(upstream, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });

    const raw = await upstreamResp.text();

    if (wantsHTML(req)) {
      // Render any returned text bubbles into HTML
      try {
        const arr = JSON.parse(raw);
        const text = Array.isArray(arr)
          ? arr
              .map((m) => (m.text ? String(m.text) : ""))
              .filter(Boolean)
              .join("\n\n")
          : raw;
        const html = marked.parse(text || "");
        return res.status(upstreamResp.status).type("html").send(html);
      } catch {
        const html = marked.parse(raw || "");
        return res.status(upstreamResp.status).type("html").send(html);
      }
    }

    res.status(upstreamResp.status);
    try {
      res.json(JSON.parse(raw));
    } catch {
      res.type("text").send(raw);
    }
  } catch (err) {
    console.error("Rasa chat proxy error:", err);
    res.status(500).json({ error: "Rasa chat proxy error", detail: String(err) });
  }
});

// Parse with Rasa NLU (intent/entities)
// Body: { text: "what can you do?" }
app.post("/rasa/parse", async (req, res) => {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }
    const { text } = req.body || {};
    if (!text) return res.status(400).json({ error: "Body must include 'text'." });

    const upstream = `${RASA_URL}/model/parse`;
    const upstreamResp = await fetch(upstream, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ text }),
    });

    const raw = await upstreamResp.text();

    // Helpful hint if NLU endpoint is missing
    if (upstreamResp.status === 404) {
      return res.status(404).json({
        description: "Not Found",
        status: 404,
        message:
          "Rasa NLU endpoint /model/parse not available. Start Rasa with `rasa run --enable-api --enable-nlu` or update your compose command.",
      });
    }

    if (wantsHTML(req)) {
      let json;
      try {
        json = JSON.parse(raw);
        const md = "```json\n" + JSON.stringify(json, null, 2) + "\n```";
        return res.status(upstreamResp.status).type("html").send(marked.parse(md));
      } catch {
        return res.status(upstreamResp.status).type("html").send(marked.parse(raw || ""));
      }
    }

    res.status(upstreamResp.status);
    try {
      res.json(JSON.parse(raw));
    } catch {
      res.type("text").send(raw);
    }
  } catch (err) {
    console.error("Rasa parse proxy error:", err);
    res.status(500).json({ error: "Rasa parse proxy error", detail: String(err) });
  }
});

// Quick Rasa status passthrough
app.get("/rasa/status", async (_req, res) => {
  try {
    const r = await fetch(`${RASA_URL}/status`, { headers: { Accept: "application/json" } });
    const raw = await r.text();
    res.status(r.status);
    try {
      res.json(JSON.parse(raw));
    } catch {
      res.type("text").send(raw);
    }
  } catch (err) {
    res.status(500).json({ error: "Failed to reach Rasa", detail: String(err) });
  }
});

// ---------- Tutor (FastAPI) proxies ----------
function tutorUrl(path) {
  // Incoming path starts with /tutor/... → strip the /tutor prefix
  // then append to TUTOR_HOST (which already ends with /tutor)
  return TUTOR_HOST + path.replace(/^\/tutor/, "");
}

// List tutors
app.get("/tutor/tutors", async (req, res) => {
  try {
    const upstream = tutorUrl(req.path);
    const r = await fetch(upstream, { headers: { Accept: "application/json" } });
    const raw = await r.text();
    res.status(r.status);
    try { res.json(JSON.parse(raw)); } catch { res.type("text").send(raw); }
  } catch (e) {
    console.error("Tutor list proxy error:", e);
    res.status(502).json({ error: "Tutor proxy error", detail: String(e) });
  }
});

// Upsert (create/update) tutor
app.post("/tutor/tutors", async (req, res) => {
  try {
    const upstream = tutorUrl(req.path);
    const r = await fetch(upstream, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(req.body),
    });
    const raw = await r.text();
    res.status(r.status);
    try { res.json(JSON.parse(raw)); } catch { res.type("text").send(raw); }
  } catch (e) {
    console.error("Tutor upsert proxy error:", e);
    res.status(502).json({ error: "Tutor proxy error", detail: String(e) });
  }
});

// Chat with a tutor
// Body: { message, history, use_rag, max_tokens }
app.post("/tutor/tutors/:id/chat", async (req, res) => {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }
    const upstream = tutorUrl(req.path);
    const r = await fetch(upstream, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: req.headers.accept || "application/json",
      },
      body: JSON.stringify(req.body),
    });
    const raw = await r.text();
    res.status(r.status);
    try { res.json(JSON.parse(raw)); } catch { res.type("text").send(raw); }
  } catch (e) {
    console.error("Tutor chat proxy error:", e);
    res.status(502).json({ error: "Tutor proxy error", detail: String(e) });
  }
});

// Optional: ingest endpoint passthrough
app.post("/tutor/tutors/:id/ingest", async (req, res) => {
  try {
    const upstream = tutorUrl(req.originalUrl); // keep querystring
    const r = await fetch(upstream, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(req.body || {}),
    });
    const raw = await r.text();
    res.status(r.status);
    try { res.json(JSON.parse(raw)); } catch { res.type("text").send(raw); }
  } catch (e) {
    console.error("Tutor ingest proxy error:", e);
    res.status(502).json({ error: "Tutor proxy error", detail: String(e) });
  }
});

// ---------- Health ----------
app.get("/healthz", (_req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`Chat UI server listening on port ${PORT}`);
  console.log(`Proxying LLM requests to ${TARGET_HOST}/v1/chat/completions`);
  console.log(`Rasa base URL: ${RASA_URL}`);
  console.log(`Tutor base URL: ${TUTOR_HOST}`);
  console.log(`Tip: add "?format=html" or send "Accept: text/html" to get rendered HTML.`);
});
