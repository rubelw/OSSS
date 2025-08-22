"use client";

import { useEffect, useState } from "react";
import { saveTokens } from "@/lib/auth-store";

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
