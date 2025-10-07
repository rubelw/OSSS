from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import httpx, os, time
from .config import settings
from .auth import require_auth
from .guardrails import redact_pii

app = FastAPI(title="Tutor Gateway", version="0.1.0")

REQS = Counter("tutor_reqs_total", "Total requests", ["route"])
TOKENS_OUT = Counter("tutor_tokens_out_total", "Total tokens out")
TOKENS_IN = Counter("tutor_tokens_in_total", "Total tokens in")

@app.get("/healthz")
async def healthz():
    return {"ok": True, "time": int(time.time())}

@app.get("/metrics")
async def metrics():
    if not settings.PROMETHEUS_ENABLED:
        raise HTTPException(404, "metrics disabled")
    data = generate_latest()
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@app.get("/v1/models")
async def list_models(_: dict | None = Depends(require_auth)):
    # proxy to upstream model server
    REQS.labels("/v1/models").inc()
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{settings.VLLM_ENDPOINT}/models")
        return JSONResponse(r.json())

@app.post("/v1/chat/completions")
async def chat_completions(req: Request, _: dict | None = Depends(require_auth)):
    REQS.labels("/v1/chat/completions").inc()
    body = await req.json()

    # enforce policy defaults if not provided by client
    body.setdefault("temperature", settings.TUTOR_TEMPERATURE)
    body.setdefault("max_tokens", settings.TUTOR_MAX_TOKENS)

    # lightweight PII redaction in the prompt (server-side caution)
    if "messages" in body:
        for m in body["messages"]:
            if isinstance(m.get("content"), str):
                m["content"] = redact_pii(m["content"])

    async with httpx.AsyncClient(timeout=60.0) as client:
        upstream = await client.post(f"{settings.VLLM_ENDPOINT}/chat/completions", json=body)
        if upstream.status_code >= 400:
            raise HTTPException(upstream.status_code, detail=upstream.text)
        data = upstream.json()

    # record token counts if present
    usage = data.get("usage") or {}
    if "prompt_tokens" in usage:
        TOKENS_IN.inc(usage["prompt_tokens"] or 0)
    if "completion_tokens" in usage:
        TOKENS_OUT.inc(usage["completion_tokens"] or 0)

    # also scrub PII from assistant output just in case
    try:
        for choice in data.get("choices", []):
            msg = choice.get("message", {})
            if isinstance(msg.get("content"), str):
                msg["content"] = redact_pii(msg["content"])
    except Exception:
        pass

    return JSONResponse(data)
