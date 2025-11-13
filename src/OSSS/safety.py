# src/OSSS/safety.py
import os, re, json
import httpx
from typing import Tuple
from pydantic import BaseModel, Field, ValidationError

# ---- Base URL resolution (guard may use its own; else fall back to main) ----
def _normalize_base(url: str | None) -> str:
    # Default to host path safe for containers AND host (you can override via env below)
    url = (url or "http://host.containers.internal:11434").rstrip("/")
    # Ensure /v1 is present exactly once
    return url if url.endswith("/v1") else (url + "/v1")

# Priority (first one found wins):
_BASE_RAW = (
    os.getenv("SAFE_OPENAI_API_BASE")
    or os.getenv("SAFE_OPENAI_BASE")
    or os.getenv("OPENAI_API_BASE")
    or os.getenv("OPENAI_BASE_URL")   # your original var
    or os.getenv("OPENAI_BASE")
    or "http://host.containers.internal:11434"
)
OPENAI_BASE = _normalize_base(_BASE_RAW)

# Key: Ollama ignores it, but OpenAI SDKs expect something. Keep it around.
OPENAI_API_KEY = os.getenv("SAFE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "ollama"

LLM_MODEL   = os.getenv("LLM_MODEL", "llama3.1")

# ----- Output shape you want to render reliably -----
class TutorReply(BaseModel):
    answer_md: str = Field(description="Markdown answer for the student")

# ----- Simple Python checks (no external deps) -----
PII_LINK_PATTERN = re.compile(
    r"(?i)("
    r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"                 # SSN-looking
    r"|https?://"
    r"|\b[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"        # email
    r"|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"                # phone
    r")"
)

def basic_input_check(text: str):
    if PII_LINK_PATTERN.search(text):
        raise ValueError("Blocked input: contains PII or link-like content.")

def basic_output_check(text: str):
    if PII_LINK_PATTERN.search(text):
        raise ValueError("Blocked output: contains PII or link-like content.")
    if not (len(text.strip()) >= 10 or re.search(r"[#*_`>\-\+]", text)):
        raise ValueError("Output too short or not markdown-like.")

# ---- Optional: remove boilerplate "safe/compliant" chatter from a guard LLM ----
_GUARD_NOISE_LINES = [
    r"^This (?:candidate )?(?:text|response) (?:appears to be )?safe(?: and compliant)?\.?$",
    r"^(?:The )?candidate text is safe\.?$",
    r"^Safe(?: and compliant)?\.?$",
    r"^No issues found.*$",
    r"^Compliant(?: with.*)?\.?$",
    r"^The text you provided seems safe and compliant to output as is\.?$",
    r"^The provided text appears safe and compliant\.?$",
    r"^The candidate text appears to be safe and compliant\.?$",
    r"^This content appears safe and compliant\.?$",
    r"^Output deemed safe and compliant\.?$",
    r"^No changes have been made\.?$",
]
_GUARD_NOISE_RX = [re.compile(pat, re.I) for pat in _GUARD_NOISE_LINES]

def strip_guard_noise(s: str) -> str:
    if not isinstance(s, str): return s
    out = s.strip()
    out = re.sub(r"^VERBATIM[:\-]?\s*", "", out, flags=re.I)
    if (out.startswith('"') and out.endswith('"')) or (out.startswith("'") and out.endswith("'")):
        out = out[1:-1]
    lines = []
    for line in out.splitlines():
        if any(rx.match(line.strip()) for rx in _GUARD_NOISE_RX):
            continue
        lines.append(line)
    return "\n".join(lines).strip()

# ----- LLM call (OpenAI-compatible /v1) -----
async def _chat_completions(messages: list) -> str:
    payload = {"model": LLM_MODEL, "messages": messages, "stream": False}
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{OPENAI_BASE}/chat/completions"
    # Example final URLs:
    #   OPENAI_BASE=http://host.containers.internal:11434/v1  -> /chat/completions (Ollama OK)
    #   OPENAI_BASE=http://localhost:11434/v1                 -> /chat/completions (host run)
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
    data = r.json()
    return (
        data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        or ""
    )

# Try to coerce to TutorReply if the model returned JSON, else treat as markdown
def coerce_to_tutor_reply(raw: str) -> str:
    s = raw.strip()
    if s.startswith("{") and s.endswith("}"):
        try:
            return TutorReply.model_validate_json(s).answer_md
        except (ValidationError, json.JSONDecodeError):
            pass
    return raw  # plain markdown or un-parseable JSON

# ----- Public entrypoint used by routes_guarded.py -----
async def guarded_chat(messages: list) -> Tuple[bool, str]:
    # 1) Pre-check (system+user only)
    try:
        user_text = "\n".join(m["content"] for m in messages if m["role"] in ("system", "user"))
        basic_input_check(user_text)
    except Exception as e:
        return True, f"Blocked (input): {e}"

    # 2) Call model
    try:
        raw = await _chat_completions(messages)
    except httpx.RequestError as e:
        # Helpful hint if someone is running on the host where host.containers.internal won't resolve
        hint = ""
        if "Name or service not known" in str(e):
            hint = (
                " (DNS resolution failed; if FastAPI is running on the host, set "
                "SAFE_OPENAI_API_BASE=http://localhost:11434/v1 or OPENAI_API_BASE likewise)"
            )
        return True, f"Upstream error: {e}{hint}"
    except Exception as e:
        return True, f"Upstream error: {e}"

    # 3) Post-check + coerce
    try:
        text = strip_guard_noise(raw)
        basic_output_check(text)
    except Exception as e:
        return True, f"Blocked (output): {e}"

    answer = coerce_to_tutor_reply(text)
    return False, answer
