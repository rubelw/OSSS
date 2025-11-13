
from __future__ import annotations

import json
import os
from typing import Any, Optional

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
from ..guardrails import redact_pii

# ---------- Optional imports with safe fallbacks ----------
#try:  # real auth dep from your project
#    from OSSS.auth.deps import require_auth  # type: ignore
#except Exception:  # safe fallback for local/dev
#    async def require_auth() -> Optional[dict]:
#        return None

async def require_auth() -> Optional[dict]:
    return None

try:
    from OSSS.config import settings  # type: ignore
except Exception:
    class _Settings:
        PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "1") not in ("0", "false", "False")
        VLLM_ENDPOINT: str = os.getenv("VLLM_ENDPOINT", "http://host.containers.internal:11434")
        TUTOR_TEMPERATURE: float = float(os.getenv("TUTOR_TEMPERATURE", "0.2"))
        TUTOR_MAX_TOKENS: int = int(os.getenv("TUTOR_MAX_TOKENS", "512"))
    settings = _Settings()  # type: ignore

# Prometheus (optional)
try:
    from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
except Exception:
    # Lightweight shims so file can import without prometheus installed
    class _DummyCounter:
        def __init__(self, *a, **kw): pass
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): return None

    def generate_latest() -> bytes:
        return b"# metrics disabled\n"

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

    Counter = _DummyCounter  # type: ignore

# HTTP client
import httpx
from pydantic import BaseModel, Field, ValidationError

# ---------- Router ----------
router = APIRouter()

# ---------- Metrics ----------
REQS = Counter("gateway_requests_total", "HTTP requests", ["path"])
TOKENS_IN = Counter("gateway_tokens_in_total", "Prompt tokens in")
TOKENS_OUT = Counter("gateway_tokens_out_total", "Completion tokens out")

# ---------- Helpers ----------
def redact_pii(text: str) -> str:
    # placeholder; plug in your redaction here
    return text

def _to_str(x: Any) -> str:
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("utf-8", "replace")
    return str(x)

# ---------- Exception Handlers (registered safely) ----------
async def _http_exc_to_json(request: Request, exc: StarletteHTTPException):
    detail: Any = exc.detail
    # Force detail to be JSON-serializable
    try:
        json.dumps(detail)
    except Exception:
        detail = _to_str(detail)
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)

async def _unexpected_exc(request: Request, exc: Exception):
    return JSONResponse({"detail": _to_str(exc)}, status_code=500)

# Register on APIRouter if available; otherwise the main app should register these
try:
    router.add_exception_handler(StarletteHTTPException, _http_exc_to_json)  # type: ignore[attr-defined]
    router.add_exception_handler(Exception, _unexpected_exc)  # type: ignore[attr-defined]
except Exception:
    # If APIRouter doesn't support this FastAPI version, main.py can call:
    #   app.add_exception_handler(StarletteHTTPException, _http_exc_to_json)
    #   app.add_exception_handler(Exception, _unexpected_exc)
    pass

# ---------- Models ----------
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = Field(default="default")
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

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
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434")
    upstream_v1 = f"{base.rstrip('/')}/v1/models"
    upstream_tags = f"{base.rstrip('/')}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(upstream_v1)
            if r.status_code == 404:
                # Ollama native
                t = await client.get(upstream_tags)
                t.raise_for_status()
                tags = t.json() or []
                # Map Ollama tags -> OpenAI model list
                data = {
                    "object": "list",
                    "data": [{"id": tag.get("name"), "object": "model", "owned_by": "ollama"} for tag in tags],
                }
                return JSONResponse(data)
            r.raise_for_status()
            return JSONResponse(r.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=str(e))


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    _: dict | None = Depends(require_auth),
):
    # Require JSON
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json",
        )

    # Raw body
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Request body is empty")

    # Parse JSON (be tolerant of a bare string body)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e.msg}")

    if isinstance(parsed, str):
        # Auto-wrap a plain prompt into a minimal OpenAI-style request
        parsed = {
            "model": getattr(settings, "DEFAULT_MODEL", "llama3.1"),
            "messages": [{"role": "user", "content": parsed}],
        }

    # Validate against your schema
    try:
        payload = ChatRequest.model_validate(parsed)
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())

    # Defaults
    if payload.temperature is None:
        payload.temperature = getattr(settings, "TUTOR_TEMPERATURE", 0.2)
    if payload.max_tokens is None:
        payload.max_tokens = getattr(settings, "TUTOR_MAX_TOKENS", 512)

    # Model aliasing
    model = (payload.model or "").strip()
    if model == "llama3":
        model = "llama3.1"

    # Redact inbound messages
    for m in payload.messages:
        if isinstance(m.content, str):
            m.content = redact_pii(m.content)

    REQS.labels("/v1/chat/completions").inc()

    # Prefer host-local Ollama by default
    base = getattr(settings, "VLLM_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
    upstream_v1 = f"{base}/v1/chat/completions"  # OpenAI-compatible (if present)
    upstream_api = f"{base}/api/chat"           # Native Ollama

    openai_req = {
        "model": model,
        "messages": [m.model_dump() for m in payload.messages],
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # 1) Try OpenAI-compatible endpoint first
            r = await client.post(upstream_v1, json=openai_req)
            if r.status_code == 404:
                # 2) Fallback to Ollama native endpoint
                ollama_req = {
                    "model": model,
                    "messages": [m.model_dump() for m in payload.messages],
                    "options": {
                        "temperature": payload.temperature,
                        # num_predict corresponds roughly to max_tokens
                        "num_predict": payload.max_tokens,
                    },
                }
                r = await client.post(upstream_api, json=ollama_req)
                if r.status_code >= 400:
                    raise HTTPException(status_code=r.status_code, detail=r.text or r.content.decode("utf-8", "replace"))

                data = r.json()

                # Ollama returns: {"message":{"role","content"},"done":true,...}
                msg = (data or {}).get("message") or {}
                out = {
                    "id": data.get("id") or "ollama-chat",
                    "object": "chat.completion",
                    "created": 0,  # Ollama's created_at is a string; skip converting here
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": msg.get("role") or "assistant",
                            "content": redact_pii(msg.get("content") or ""),
                        },
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                try:
                    TOKENS_IN.inc(0); TOKENS_OUT.inc(0)
                except Exception:
                    pass
                return JSONResponse(out)

            # If OpenAI-compatible endpoint responded with something else
            if r.status_code >= 400:
                raise HTTPException(status_code=r.status_code, detail=r.text or r.content.decode("utf-8", "replace"))

            data = r.json()

            # Metrics from OpenAI-style usage, if present
            usage = data.get("usage") or {}
            try:
                TOKENS_IN.inc(usage.get("prompt_tokens") or 0)
                TOKENS_OUT.inc(usage.get("completion_tokens") or 0)
            except Exception:
                pass

            # Redact outbound assistant content
            for choice in data.get("choices", []):
                msg = choice.get("message") or {}
                if isinstance(msg.get("content"), str):
                    msg["content"] = redact_pii(msg["content"])

            return JSONResponse(data)

        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=str(e))