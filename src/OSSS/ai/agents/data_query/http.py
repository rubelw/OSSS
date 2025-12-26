# src/OSSS/ai/agents/data_views/http.py
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx


async def http_request(
    *,
    method: str,
    base_url: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json: Any = None,
    timeout_s: float = 10.0,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    start = time.time()

    ok = True
    error: Optional[str] = None
    status_code: Optional[int] = None
    data: Any = None

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.request(method, url, params=params, json=json)
            status_code = resp.status_code
            try:
                data = resp.json()
            except Exception:
                data = resp.text

            if resp.is_error:
                ok = False
                error = f"HTTP {resp.status_code}"
    except Exception as e:
        ok = False
        error = repr(e)

    elapsed_ms = int((time.time() - start) * 1000)

    return {
        "ok": ok,
        "method": method,
        "url": url,
        "path": path,
        "params": params or {},
        "status_code": status_code,
        "data": data,
        "error": error,
        "elapsed_ms": elapsed_ms,
    }