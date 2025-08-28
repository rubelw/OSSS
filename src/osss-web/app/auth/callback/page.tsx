// src/osss-web/app/auth/callback/page.tsx
"use client";

import { useEffect, useState } from "react";

/**
 * Minimal client-side token store for the OAuth fragment/callback flow.
 * Persists tokens in localStorage (adjust to cookies/secure storage if needed).
 */
function saveTokens(args: {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number; // seconds
}) {
  try {
    const now = Date.now();
    const expiresAt = args.expires_in ? now + args.expires_in * 1000 : undefined;

    const payload = {
      access_token: args.access_token,
      refresh_token: args.refresh_token,
      token_type: args.token_type ?? "Bearer",
      expires_at: expiresAt, // epoch ms
      saved_at: now,
    };

    // NOTE: For production, prefer HTTP-only cookies or a server session.
    localStorage.setItem("osss.tokens", JSON.stringify(payload));
  } catch {
    // swallow; caller will log if needed
  }
}

function parseHash(hash: string) {
  const out: Record<string, string> = {};
  const h = hash.startsWith("#") ? hash.slice(1) : hash;
  for (const part of h.split("&")) {
    const [k, v] = part.split("=");
    if (k) out[decodeURIComponent(k)] = decodeURIComponent(v || "");
  }
  return out;
}

export default function OAuthCallback() {
  const [msg, setMsg] = useState("Finalizing sign-in…");

  useEffect(() => {
    try {
      // Prefer fragment (#…), fallback to query (?…)
      const hash = window.location.hash || "";
      const qp = new URLSearchParams(window.location.search);

      let params: Record<string, string> = {};
      if (hash.includes("access_token")) {
        params = parseHash(hash);
      } else if (qp.get("access_token")) {
        qp.forEach((v, k) => (params[k] = v));
      }

      if (!params["access_token"]) {
        setMsg("No access_token found in callback.");
        return;
      }

      // Save and go home
      saveTokens({
        access_token: params["access_token"],
        refresh_token: params["refresh_token"] || undefined,
        token_type: params["token_type"] || undefined,
        expires_in: params["expires_in"] ? Number(params["expires_in"]) : undefined,
      });

      setMsg("Signed in! Redirecting…");
      const next = sessionStorage.getItem("osss.postLoginRedirect") || "/";
      sessionStorage.removeItem("osss.postLoginRedirect");
      window.location.replace(next);
    } catch (e) {
      setMsg("Failed to process callback.");
      // eslint-disable-next-line no-console
      console.error(e);
    }
  }, []);

  return (
    <div style={{ padding: 24 }}>
      <h1>Signing you in…</h1>
      <p>{msg}</p>
    </div>
  );
}
