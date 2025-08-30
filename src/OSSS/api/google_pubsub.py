# src/OSSS/api/google_pubsub.py
from fastapi import APIRouter, Header, HTTPException, Depends, Request
from OSSS.core.settings_google import GoogleSettings
import base64
import json

router = APIRouter(prefix="/api/google", tags=["google"])

@router.post("/pubsub/push")
async def pubsub_push(
    request: Request,
    settings: GoogleSettings = Depends(),
    x_cloud_tasks_taskname: str | None = Header(default=None),
):
    body = await request.json()
    # Optional: verify a shared token in attributes
    msg = body.get("message", {})
    attrs = msg.get("attributes", {}) or {}
    token = attrs.get("verificationToken")
    if settings.pubsub_verification_token and token != settings.pubsub_verification_token:
        raise HTTPException(403, "Bad verification token")

    data_b64 = msg.get("data")
    if data_b64:
        payload = json.loads(base64.b64decode(data_b64))
        # payload will include resource name & event type
        # schedule or trigger a targeted sync (e.g., sync specific course rosters)
        # keep the handler fast — push heavy work to a background worker/queue
    return {"ok": True}
