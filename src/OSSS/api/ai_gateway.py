
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
try:  # real auth dep from your project
    from OSSS.auth.deps import require_auth  # type: ignore
except Exception:  # safe fallback for local/dev
    async def require_auth() -> Optional[dict]:
        return None

try:
    from OSSS.config import settings  # type: ignore
except Exception:
    class _Settings:
        PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "1") not in ("0", "false", "False")
        VLLM_ENDPOINT: str = os.getenv("VLLM_ENDPOINT", "http://ollama:11434/v1")
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
    # vLLM OpenAI-compatible servers usually expose GET /models; some use /v1/models
    base = getattr(settings, "VLLM_ENDPOINT", "http://ollama:11434/v1")
    url_candidates = [
        f"{base}/models",
        f"{base.rstrip('/')}/v1/models",
    ]
    last_exc: Optional[Exception] = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        for u in url_candidates:
            try:
                r = await client.get(u)
                if r.status_code < 400:
                    return JSONResponse(r.json())
                last_exc = HTTPException(status_code=r.status_code, detail=r.text)
            except Exception as e:
                last_exc = e
    if isinstance(last_exc, HTTPException):
        raise last_exc
    raise HTTPException(status_code=502, detail=_to_str(last_exc or "upstream error"))

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    _: dict | None = Depends(require_auth),
    raw: bytes | None = Body(default=None),
):
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json",
        )

    if not raw:
        raise HTTPException(status_code=400, detail="Request body is empty")

    try:
        payload = ChatRequest.model_validate_json(raw)
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=_to_str(ve))

    # Defaults
    if payload.temperature is None:
        payload.temperature = getattr(settings, "TUTOR_TEMPERATURE", 0.2)
    if payload.max_tokens is None:
        payload.max_tokens = getattr(settings, "TUTOR_MAX_TOKENS", 512)

    # Redact
    for m in payload.messages:
        m.content = redact_pii(m.content)

    REQS.labels("/v1/chat/completions").inc()

    upstream_url = f"{getattr(settings, 'VLLM_ENDPOINT', 'http://ollama:11434/v1')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(upstream_url, json=payload.model_dump())
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=_to_str(e))

    if r.status_code >= 400:
        detail = r.text if r.text else _to_str(r.content)
        raise HTTPException(status_code=r.status_code, detail=detail)

    # If upstream isn't JSON, pass bytes through untouched
    try:
        data = r.json()
    except ValueError:
        return Response(content=r.content, media_type=r.headers.get("content-type", "text/plain"))

    # Metrics
    usage = data.get("usage") or {}
    try:
        TOKENS_IN.inc(usage.get("prompt_tokens") or 0)
        TOKENS_OUT.inc(usage.get("completion_tokens") or 0)
    except Exception:
        pass

    # Scrub assistant output
    try:
        for choice in data.get("choices", []):
            msg = choice.get("message", {})
            if isinstance(msg.get("content"), str):
                msg["content"] = redact_pii(msg["content"])
    except Exception:
        pass

    return JSONResponse(data)
