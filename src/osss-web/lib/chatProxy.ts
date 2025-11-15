// src/osss-web/lib/chatProxy.ts
export const TARGET_HOST =
  process.env.TARGET_HOST ?? "http://host.docker.internal:8081";

export const RASA_URL =
  process.env.RASA_URL ?? "http://rasa-mentor:5005";

export const SAFE_BASE = process.env.SAFE_BASE ?? TARGET_HOST;
export const SAFE_PATH = process.env.SAFE_PATH ?? "/v1/chat/safe";

export const TUTOR_HOST = (
  process.env.TUTOR_HOST ?? `${TARGET_HOST}/tutor`
).replace(/\/+$/, "");

export function tutorUrl(path: string) {
  // path starts like /tutor/..., we map it to TUTOR_HOST + /...
  return TUTOR_HOST + path.replace(/^\/tutor/, "");
}

// From server.js: clean up boilerplate guard noise
export function stripGuardNoise(s: string): string {
  if (typeof s !== "string") return s as any;
  let out = s.trim();

  out = out.replace(/^VERBATIM[:\-]?\s*/i, "");
  if (
    (out.startsWith('"') && out.endsWith('"')) ||
    (out.startsWith("'") && out.endsWith("'"))
  ) {
    out = out.slice(1, -1);
  }

  const drop = [
    /^(?:this )?candidate (?:text|response) (?:appears to be )?safe(?: and compliant)?\.?$/i,
    /^(?:the )?candidate text is safe\.?$/i,
    /^safe(?: and compliant)?\.?$/i,
    /^no issues found.*$/i,
    /^compliant(?: with.*)?\.?$/i,
    /^the text you provided seems safe and compliant to output as is\.?$/i,
    /^the provided text appears safe and compliant\.?$/i,
    /^the candidate text appears to be safe and compliant\.?$/i,
    /^this content appears safe and compliant\.?$/i,
    /^output deemed safe and compliant\.?$/i,
    /^no changes have been made\.?$/i,
  ];

  out = out
    .split(/\r?\n/)
    .filter((line) => !drop.some((rx) => rx.test(line.trim())))
    .join("\n")
    .trim();

  return out;
}

// From server.js: join Rasa bubbles into one text string
export function joinRasaBubbles(raw: string): string {
  try {
    const arr = JSON.parse(raw);

    if (Array.isArray(arr)) {
      // Extract and clean message bubbles
      let candidate = arr
        .map((m) =>
          (m.text ?? m.image ?? (typeof m.custom === "string" ? m.custom : "") ?? "")
            .toString()
            .trim()
        )
        .filter(Boolean)
        .join("\n"); // ← single newline, not "\n\n"

      // Collapse accidental multiple newlines (3+ → 1)
      candidate = candidate.replace(/\n{2,}/g, "\n").trim();

      return candidate;
    }

    return typeof arr === "string" ? arr.trim() : raw;
  } catch {
    return raw;
  }
}
