# src/OSSS/safety.py
import os, re, json
import httpx
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError

OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "http://ollama:11434/v1")
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

# ----- LLM call (OpenAI-compatible /v1) -----
async def _chat_completions(messages: list) -> str:
    payload = {"model": LLM_MODEL, "messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{OPENAI_BASE}/chat/completions", json=payload)
        r.raise_for_status()
    data = r.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""

# Try to coerce to TutorReply if the model returned JSON, else treat as markdown
def coerce_to_tutor_reply(raw: str) -> str:
    s = raw.strip()
    if s.startswith("{") and s.endswith("}"):
        try:
            return TutorReply.model_validate_json(s).answer_md
        except ValidationError:
            pass
        except json.JSONDecodeError:
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
    raw = await _chat_completions(messages)

    # 3) Post-check + coerce
    try:
        basic_output_check(raw)
    except Exception as e:
        return True, f"Blocked (output): {e}"

    answer = coerce_to_tutor_reply(raw)
    return False, answer
