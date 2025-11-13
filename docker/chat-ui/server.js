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

// FastAPI "safe" endpoint (usually same host as TARGET_HOST)
const SAFE_BASE = process.env.SAFE_BASE || TARGET_HOST;
const SAFE_PATH = process.env.SAFE_PATH || "/v1/chat/safe";

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

function joinRasaBubbles(raw) {
  try {
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) {
      return arr
        .map(m => m.text || m.image || (typeof m.custom === "string" ? m.custom : ""))
        .filter(Boolean)
        .join("\n\n");
    }
    return typeof arr === "string" ? arr : raw;
  } catch {
    return raw;
  }
}

function stripGuardNoise(s) {
  if (typeof s !== "string") return s;
  let out = s.trim();

  // Remove VERBATIM prefix and wrapping quotes
  out = out.replace(/^VERBATIM[:\-]?\s*/i, "");
  if ((out.startsWith('"') && out.endsWith('"')) ||
      (out.startsWith("'") && out.endsWith("'"))) {
    out = out.slice(1, -1);
  }

  // Patterns for boilerplate safety lines
  const drop = [
    /^(?:this )?candidate (?:text|response) (?:appears to be )?safe(?: and compliant)?\.?$/i,
    /^(?:the )?candidate text is safe\.?$/i,
    /^safe(?: and compliant)?\.?$/i,
    /^no issues found.*$/i,
    /^compliant(?: with.*)?\.?$/i,
    /^the text you provided seems safe and compliant to output as is\.?$/i,
    /^the provided text appears safe and compliant\.?$/i,
    /^the candidate text appears to be safe and compliant\.?$/i, // NEW
    /^this content appears safe and compliant\.?$/i,
    /^output deemed safe and compliant\.?$/i,
    /^no changes have been made\.?$/i // NEW
  ];

  // Remove any line that matches a boilerplate pattern
  out = out
    .split(/\r?\n/)
    .filter(line => !drop.some(rx => rx.test(line.trim())))
    .join("\n")
    .trim();

  return out;
}

// ---------- LLM chat proxies ----------
async function handleChatProxy(req, res, { forceHtml = false, upstreamPath = "/v1/chat/completions" } = {}) {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }
    const body = req.body;
    if (!body || !Array.isArray(body.messages) || body.messages.length === 0) {
      return res.status(400).json({ error: "Request must include messages array" });
    }

    const upstream = `${TARGET_HOST}${upstreamPath}`;
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
      const text = stripGuardNoise(extractTextFromUpstream(json));
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
// Legacy OpenAI-compatible path
app.post("/v1/chat/completions", (req, res) =>
  handleChatProxy(req, res, { forceHtml: false, upstreamPath: "/v1/chat/completions" })
);
// Guarded path (FastAPI safety endpoint)
app.post("/v1/chat/safe", (req, res) =>
  handleChatProxy(req, res, { forceHtml: false, upstreamPath: "/v1/chat/safe" })
);
// Always-HTML helpers (optional)
app.post("/chat-html", (req, res) =>
  handleChatProxy(req, res, { forceHtml: true, upstreamPath: "/v1/chat/completions" })
);
app.post("/chat-safe-html", (req, res) =>
  handleChatProxy(req, res, { forceHtml: true, upstreamPath: "/v1/chat/safe" })
);

// ---------- Rasa proxies ----------
// Chat with Rasa, then pass the response through the FastAPI /v1/chat/safe guard
// Body: { sender: "user-id", message: "hi there" }
app.post("/rasa/chat-safe", async (req, res) => {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }
    const { sender, message, metadata } = req.body || {};
    if (!message) return res.status(400).json({ error: "Body must include 'message'." });

    // 1) Ask Rasa first
    const rasaPayload = {
      sender: sender || "user",
      message,
      ...(metadata ? { metadata } : {}),
    };
    const rasaResp = await fetch(`${RASA_URL}/webhooks/rest/webhook`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(rasaPayload),
    });
    const rasaRaw = await rasaResp.text();

    // If Rasa failed, bubble the failure up
    if (!rasaResp.ok) {
      res.status(rasaResp.status);
      try { return res.json(JSON.parse(rasaRaw)); }
      catch { return res.type("text").send(rasaRaw); }
    }

    // 2) Normalize Rasa bubbles into one candidate reply
    const candidate = joinRasaBubbles(rasaRaw) || "";

    // 3) Send candidate through the guard
    //    System prompt tells the guard to pass through safe text verbatim,
    //    otherwise refuse/trim.
    const guardMessages = [
      {
        role: "system",
        content:
          "You are an output safety gateway. If the provided 'candidate' text is safe and compliant, " +
          "return it VERBATIM as your message. If unsafe, refuse with a brief safe alternative.",
      },
      { role: "user", content: `candidate:\n${candidate}` },
    ];

    const safeResp = await fetch(`${SAFE_BASE}${SAFE_PATH}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        // Forward auth if you use it on the FastAPI side:
        Authorization: req.get("Authorization") || "",
      },
      body: JSON.stringify({
        model: "llama3.1",
        messages: guardMessages,
        temperature: 0.2,
        max_tokens: 512,
        stream: false,
      }),
    });

    const safeRaw = await safeResp.text();

    // If the guard returned HTML and the client wants HTML, just pass it through
    if (wantsHTML(req) && (safeResp.headers.get("content-type") || "").toLowerCase().includes("text/html")) {
      return res.status(safeResp.status).type("html").send(safeRaw);
    }

    // Try JSON parse of guard result
    let safeJson;
    try { safeJson = JSON.parse(safeRaw); } catch { /* leave undefined */ }

    if (!safeResp.ok) {
      // Show guard reason / payload
      const reason =
        safeJson?.detail?.reason ||
        safeJson?.detail ||
        safeJson ||
        safeRaw ||
        ("HTTP " + safeResp.status);
      return res.status(safeResp.status).json({ error: "guard_block", detail: reason });
    }

    // 4) Success: extract message content from guard
    let guarded =
      safeJson?.message?.content ??
      safeJson?.choices?.[0]?.message?.content ??
      safeJson?.choices?.[0]?.text ??
      safeRaw;

    // Clean up guard output
    if (typeof guarded === "string") {
      guarded = guarded.trim();

      // Remove VERBATIM: label (case-insensitive)
      guarded = guarded.replace(/^VERBATIM[:\-]?\s*/i, "");

      // Remove wrapping quotes
      if ((guarded.startsWith('"') && guarded.endsWith('"')) ||
          (guarded.startsWith("'") && guarded.endsWith("'"))) {
        guarded = guarded.slice(1, -1);
      }

      // Remove generic “safe/compliant” confirmation lines
      guarded = guarded.replace(
        /This candidate response appears to be safe and compliant.*$/i,
        ""
      ).trim();
    }


    // If the client asked for HTML, render Markdown nicely
    if (wantsHTML(req)) {
      return res.status(200).type("html").send(marked.parse(guarded || ""));
    }

    // Otherwise, return JSON in the same "Rasa-like array" shape so the UI path stays simple
    return res.status(200).json([{ recipient_id: sender || "user", text: guarded }]);

  } catch (err) {
    console.error("Rasa chat-safe proxy error:", err);
    res.status(500).json({ error: "Rasa chat-safe proxy error", detail: String(err) });
  }
});

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
// Chat with a tutor — ALWAYS guarded through /v1/chat/safe
app.post("/tutor/tutors/:id/chat", async (req, res) => {
  try {
    if (!req.is("application/json")) {
      return res.status(400).json({ error: "Only application/json is accepted" });
    }

    // 1) Call upstream Tutor /chat first (to get the candidate + sources)
    const upstream = tutorUrl(req.path); // maps /tutor/... to ${TUTOR_HOST}/...
    const tutorResp = await fetch(upstream, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(req.body || {})
    });
    const tutorRaw = await tutorResp.text();

    if (!tutorResp.ok) {
      res.status(tutorResp.status);
      try { return res.json(JSON.parse(tutorRaw)); }
      catch { return res.type("text").send(tutorRaw); }
    }

    // 2) Normalize Tutor reply -> candidate + keep sources
    let tutorJson;
    try { tutorJson = JSON.parse(tutorRaw); } catch { tutorJson = tutorRaw; }

    const candidate =
      (tutorJson && typeof tutorJson === "object" && "answer" in tutorJson)
        ? String(tutorJson.answer || "")
        : (typeof tutorJson === "string" ? tutorJson : JSON.stringify(tutorJson));

    const sources =
      (tutorJson && typeof tutorJson === "object" && Array.isArray(tutorJson.sources))
        ? tutorJson.sources
        : [];

    // 3) Run candidate through guard (/v1/chat/safe)
    const guardMessages = [
      {
        role: "system",
        content:
          "You are an output safety gateway. If the provided 'candidate' text is safe and compliant, " +
          "return it VERBATIM as your message. If unsafe, refuse with a brief safe alternative."
      },
      { role: "user", content: `candidate:\n${candidate}` }
    ];

    const safeResp = await fetch(`${SAFE_BASE}${SAFE_PATH}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: req.get("Authorization") || ""
      },
      body: JSON.stringify({
        model: "llama3.1",
        messages: guardMessages,
        temperature: 0.2,
        max_tokens: 512,
        stream: false
      })
    });

    const safeRaw = await safeResp.text();
    let safeJson;
    try { safeJson = JSON.parse(safeRaw); } catch {}

    if (!safeResp.ok) {
      const reason =
        safeJson?.detail?.reason ||
        safeJson?.detail ||
        safeJson ||
        safeRaw ||
        ("HTTP " + safeResp.status);
      return res.status(safeResp.status).json({ error: "guard_block", detail: reason });
    }

    // 4) Extract + clean final answer
    let guarded =
      safeJson?.message?.content ??
      safeJson?.choices?.[0]?.message?.content ??
      safeJson?.choices?.[0]?.text ??
      safeRaw;

    guarded = stripGuardNoise(guarded || "");

    // 5) Return Tutor-shaped JSON so the UI remains unchanged
    return res.status(200).json({ answer: guarded, sources });

  } catch (e) {
    console.error("Tutor chat (guarded) proxy error:", e);
    res.status(502).json({ error: "Tutor chat (guarded) proxy error", detail: String(e) });
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
