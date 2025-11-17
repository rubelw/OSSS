from __future__ import annotations

import json
import os
from typing import Any, Optional, List, Literal, Union

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException

# If you have a real redactor, import it here
def redact_pii(text: str) -> str:
    return text

# ---------- Auth (safe fallback) ----------
async def require_auth() -> Optional[dict]:
    return None

# ---------- Settings (safe fallback) ----------
try:
    from OSSS.config import settings  # type: ignore
except Exception:
    class _Settings:
        PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "1") not in ("0", "false", "False")
        VLLM_ENDPOINT: str = os.getenv("VLLM_ENDPOINT", "http://host.containers.internal:11434")
        TUTOR_TEMPERATURE: float = float(os.getenv("TUTOR_TEMPERATURE", "0.2"))
        TUTOR_MAX_TOKENS: int = int(os.getenv("TUTOR_MAX_TOKENS", "2048"))
        DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama3.1")
    settings = _Settings()  # type: ignore

# ---------- Metrics (optional) ----------
try:
    from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
except Exception:
    class _DummyCounter:
        def __init__(self, *a, **kw): pass
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): return None
    def generate_latest() -> bytes: return b"# metrics disabled\n"
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    Counter = _DummyCounter  # type: ignore

REQS = Counter("gateway_requests_total", "HTTP requests", ["path"])
TOKENS_IN = Counter("gateway_tokens_in_total", "Prompt tokens in")
TOKENS_OUT = Counter("gateway_tokens_out_total", "Completion tokens out")

# ---------- HTTP client ----------
import httpx
from pydantic import BaseModel, Field

# ---------- Router ----------
router = APIRouter()

# ---------- Exception helpers ----------
def _to_str(x: Any) -> str:
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("utf-8", "replace")
    return str(x)

async def _http_exc_to_json(request: Request, exc: StarletteHTTPException):
    detail: Any = exc.detail
    try:
        json.dumps(detail)
    except Exception:
        detail = _to_str(detail)
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)

async def _unexpected_exc(request: Request, exc: Exception):
    return JSONResponse({"detail": _to_str(exc)}, status_code=500)

try:
    router.add_exception_handler(StarletteHTTPException, _http_exc_to_json)  # type: ignore[attr-defined]
    router.add_exception_handler(Exception, _unexpected_exc)  # type: ignore[attr-defined]
except Exception:
    pass

# ---------- Models ----------
class ChatMessage(BaseModel):

    role: Literal["system", "user", "assistant"] = Field(
        description="The role of the message sender (system, user, or assistant).",
        examples=["system", "user", "assistant"],
    )
    content: str = Field(
        description="The text content of the message.",
        examples=["You are a helpful assistant.", "How do I cook pasta al dente?"],
    )


class ChatRequest(BaseModel):
    model: Optional[str] = Field(default="llama3.1", description="Model name (e.g., llama3.1)")
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = False


# ---------- Endpoints ----------
@router.get("/metrics")
async def metrics():
    if not getattr(settings, "PROMETHEUS_ENABLED", False):
        raise HTTPException(status_code=404, detail="metrics disabled")
    data = generate_latest()
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@router.get("/v1/models")
async def list_models(_: dict | None = Depends(require_auth)):
    REQS.labels("/v1/models").inc()
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    upstream_v1 = f"{base}/v1/models"
    upstream_tags = f"{base}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(upstream_v1)
            if r.status_code == 404:
                # Ollama native (/api/tags returns {"models":[...]})
                t = await client.get(upstream_tags)
                t.raise_for_status()
                tags = t.json() or {}
                models = tags.get("models", [])
                data = {
                    "object": "list",
                    "data": [{"id": m.get("name"), "object": "model", "owned_by": "ollama"} for m in models],
                }
                return JSONResponse(data)
            r.raise_for_status()
            return JSONResponse(r.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=str(e))

@router.post("/v1/chat/completions")
async def chat_completions(
    payload: ChatRequest = Body(
        ...,
        example={
            "model": "llama3.1",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "How do I cook pasta al dente?"}
            ],
            "temperature": 0.2,
            "max_tokens": 256,
            "stream": False
        },
        description="OpenAI-style chat completion request body."
    ),
    _: dict | None = Depends(require_auth),
):
    """
    Accepts either:
      • OpenAI-style JSON body (model, messages, …)
      • A plain string body (auto-wrapped into a minimal request)
    """
    # Normalize to ChatRequest
    if isinstance(payload, str):
        payload = ChatRequest(
            model=getattr(settings, "DEFAULT_MODEL", "llama3.1"),
            messages=[ChatMessage(role="user", content=payload)],
            temperature=getattr(settings, "TUTOR_TEMPERATURE", 0.2),
            max_tokens=getattr(settings, "TUTOR_MAX_TOKENS", 2048),
            stream=False,
        )

    # Defaults
    model = (payload.model or getattr(settings, "DEFAULT_MODEL", "llama3.1")).strip()
    if model == "llama3":  # simple alias
        model = "llama3.1"

    temperature = (
        payload.temperature
        if payload.temperature is not None
        else getattr(settings, "TUTOR_TEMPERATURE", 0.2)
    )

    # ----- Option A: enforce a minimum completion size -----
    DEFAULT_MAX_TOKENS = getattr(settings, "TUTOR_MAX_TOKENS", 2048)
    MIN_COMPLETION_TOKENS = getattr(settings, "MIN_COMPLETION_TOKENS", 512)

    requested = payload.max_tokens

    if requested is None:
        # No explicit max_tokens from client → use default
        max_tokens = DEFAULT_MAX_TOKENS
    else:
        # Client provided a value → enforce a floor so we don't chop answers
        max_tokens = max(requested, MIN_COMPLETION_TOKENS)
    # ------------------------------------------------------

    # Redact inbound
    for m in payload.messages:
        m.content = redact_pii(m.content)

    REQS.labels("/v1/chat/completions").inc()

    base = getattr(settings, "VLLM_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
    upstream_v1 = f"{base}/v1/chat/completions"  # OpenAI-compatible
    upstream_api = f"{base}/api/chat"            # Ollama native

    openai_req = {
        "model": model,
        "messages": [m.model_dump() for m in payload.messages],
        "temperature": temperature,
        "stream": False,
    }

    if max_tokens is not None:
        openai_req["max_tokens"] = max_tokens

    timeout = httpx.Timeout(
        connect=10.0,
        read=None,  # allow long responses
        write=10.0,
        pool=10.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(upstream_v1, json=openai_req)

            print(
                f"[chat_completions] upstream_v1 status={r.status_code} "
                f"bytes={len(r.content)}"
            )

            # Decide whether to fall back to Ollama native
            fallback = False
            if r.status_code == 404:
                fallback = True
            elif r.status_code == 400:
                # Some Ollama builds return 400 with {"error":{"message":"model is required"...}}
                try:
                    j = r.json()
                    err = (j or {}).get("error") or {}
                    msg = (err.get("message") or "").lower()
                    if any(s in msg for s in (
                            "model is required",
                            "model not found",
                            "no such model",
                            "unknown model",
                    )):
                        fallback = True
                except Exception:
                    # If we can't parse the error, don't fallback blindly
                    pass

            if fallback:
                # Fallback to Ollama native /api/chat
                options: dict = {
                    "temperature": temperature,
                }

                if max_tokens is not None:
                    # num_predict ~= max_tokens in Ollama
                    options["num_predict"] = max_tokens

                ollama_req = {
                    "model": model,
                    "messages": [m.model_dump() for m in payload.messages],
                    "options": options,
                    "stream": False,
                }

                r = await client.post(upstream_api, json=ollama_req)
                if r.status_code >= 400:
                    raise HTTPException(
                        status_code=r.status_code,
                        detail=r.text or r.content.decode("utf-8", "replace"),
                    )

                data = r.json()
                msg = (data or {}).get("message") or {}
                out = {
                    "id": data.get("id") or "ollama-chat",
                    "object": "chat.completion",
                    "created": 0,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": msg.get("role") or "assistant",
                            "content": redact_pii(msg.get("content") or ""),
                        },
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
                try:
                    TOKENS_IN.inc(0)
                    TOKENS_OUT.inc(0)
                except Exception:
                    pass
                return JSONResponse(out)

            # If OpenAI-compatible endpoint responded with something else
            if r.status_code >= 400:
                raise HTTPException(
                    status_code=r.status_code,
                    detail=r.text or r.content.decode("utf-8", "replace"),
                )

            data = r.json()

            # -------- DEBUG + optional auto-continue on bad tail --------
            try:
                choices = data.get("choices") or []
                first = choices[0] if choices else {}
                finish_reason = first.get("finish_reason")
                usage = data.get("usage") or {}
                msg = first.get("message") or {}
                content = msg.get("content", "")

                print(
                    "[/ai/chat/rag] finish_reason=",
                    finish_reason,
                    " prompt_tokens=",
                    usage.get("prompt_tokens"),
                    " completion_tokens=",
                    usage.get("completion_tokens"),
                    " content_len=",
                    len(content),
                )
                print("[/ai/chat/rag] content tail:", repr(content[-200:]))

                # --- Heuristic: did we stop right after starting Consequences? ---
                stripped = content.strip()
                bad_tail = (
                        stripped.endswith("**Consequences**")
                        or stripped.endswith("**Consequences**\n*")
                        or stripped.endswith("**Consequences**\n\n*")
                        or stripped.endswith("\n**Consequences**\n\n*")
                )

                # Only try to auto-continue if we actually have some text
                # AND we hit our heuristic pattern.
                if bad_tail:
                    print("[/ai/chat/rag] Detected truncated Consequences section, auto-continuing…")

                    # Build a follow-up request that tells the model to finish the list.
                    followup_messages = [m.model_dump() for m in payload.messages]
                    followup_messages.append({
                        "role": "user",
                        "content": (
                            "Please continue your previous answer. You just started the "
                            "'Consequences' section and then stopped at a single bullet. "
                            "Finish listing the consequences clearly as bullet points or "
                            "short paragraphs, without repeating the entire earlier answer."
                        ),
                    })

                    followup_req = {
                        "model": model,
                        "messages": followup_messages,
                        "temperature": temperature,
                        "stream": False,
                    }
                    if max_tokens is not None:
                        followup_req["max_tokens"] = max_tokens

                    r2 = await client.post(upstream_v1, json=followup_req)
                    if r2.status_code < 400:
                        data2 = r2.json()
                        choices2 = data2.get("choices") or []
                        if choices2:
                            msg2 = (choices2[0].get("message") or {})
                            extra = msg2.get("content") or ""
                            print(
                                "[/ai/chat/rag] auto-continue added",
                                len(extra),
                                "chars"
                            )
                            # Append continuation to original content
                            msg["content"] = content.rstrip() + "\n\n" + extra

                            # Optionally, update finish_reason to whatever the second call had
                            first["finish_reason"] = choices2[0].get("finish_reason") or "stop"
                    else:
                        print(
                            "[/ai/chat/rag] auto-continue followup failed "
                            f"status={r2.status_code}"
                        )

            except Exception as e:
                print("[/ai/chat/rag] debug/auto-continue inspection failed:", e)
            # --------------------------------------------------------

            # Metrics (OpenAI-style)
            usage = data.get("usage") or {}
            try:
                TOKENS_IN.inc(usage.get("prompt_tokens") or 0)
                TOKENS_OUT.inc(usage.get("completion_tokens") or 0)
            except Exception:
                pass

            # Redact outbound
            for choice in data.get("choices", []):
                msg = choice.get("message") or {}
                if isinstance(msg.get("content"), str):
                    msg["content"] = redact_pii(msg["content"])

            # --- Clean up stray trailing Markdown bullets like "*" after headers ---
            for choice in data.get("choices", []):
                msg = choice.get("message") or {}
                content = msg.get("content", "")

                # Remove cases like:
                # "Consequences\n\n*"
                content = content.replace("**Consequences**\n\n*", "**Consequences**\n")
                content = content.replace("Consequences\n\n*", "Consequences\n")

                # Remove any line that ONLY contains "*"
                cleaned_lines = []
                for line in content.splitlines():
                    if line.strip() == "*":
                        continue
                    cleaned_lines.append(line)
                msg["content"] = "\n".join(cleaned_lines)

            return JSONResponse(data)

        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=str(e))
