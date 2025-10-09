# src/OSSS/sessions_diag.py  (or wherever you added your diag routes)
from fastapi import APIRouter, Depends, Query
from OSSS.sessions import get_session_store, RedisSession, SESSION_PREFIX
from OSSS.app_logger import get_logger
import json

log = get_logger("sessions.diag")
router = APIRouter()

@router.get("/_session_list", tags=["_debug"])
async def session_list(
    limit: int = Query(100, ge=1, le=500),
    include_preview: bool = Query(False),
    preview_len: int = Query(120, ge=1, le=4000),
    store: RedisSession = Depends(get_session_store),
):
    items = []
    async for key in store.iter_keys(limit=limit):
        ttl = await store.ttl(key)
        entry = {"key": key, "ttl": ttl}
        if include_preview:
            raw = await store.get(key, as_json=False)
            entry["preview"] = (raw[:preview_len] if isinstance(raw, str) else None)
        items.append(entry)
    log.info("Listed %d session(s)", len(items))
    return {"count": len(items), "sessions": items}

@router.get("/_session_ttl", tags=["_debug"])
async def session_ttl(key: str = Query(...), store: RedisSession = Depends(get_session_store)):
    ttl = await store.ttl(key)
    return {"key": key, "ttl": ttl}

@router.post("/_session_set_demo", tags=["_debug"])
async def session_set_demo(
    key: str = Query(...),
    ttl: int = Query(3600, ge=1),
    value: str | None = Query(None, description="JSON string; omit to use default"),
    store: RedisSession = Depends(get_session_store),
):
    payload = {"hello": "world"}  # default
    if value and value.strip():
        try:
            payload = json.loads(value)
        except Exception:
            payload = value  # store raw string
    await store.set(key, payload, ttl=ttl)
    now_ttl = await store.ttl(key)
    log.info("Demo set key=%s ttl=%s", key, now_ttl)
    return {"ok": True, "key": key, "ttl": now_ttl}
