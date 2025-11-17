from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/metagpt", tags=["metagpt"])

METAGPT_URL = os.getenv("METAGPT_URL", "http://metagpt:8001").rstrip("/")


class MetaGPTRequest(BaseModel):
    requirement: str
    investment: float | None = 2.0
    workspace: str | None = None


class MetaGPTResponse(BaseModel):
    message: str
    workspace: str | None = None


@router.post("/osss-agent", response_model=MetaGPTResponse)
async def launch_osss_metagpt_agent(payload: MetaGPTRequest) -> MetaGPTResponse:
    """
    Thin HTTP client that forwards the request to the MetaGPT sidecar.
    No direct import of `metagpt` in this container.
    """
    if not METAGPT_URL:
        raise HTTPException(status_code=503, detail="MetaGPT sidecar URL not configured")

    req_body = {
        "requirement": payload.requirement,
        "investment": payload.investment or 2.0,
    }
    if payload.workspace:
        req_body["workspace"] = payload.workspace

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{METAGPT_URL}/run", json=req_body)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MetaGPT sidecar not available: {exc}",
        ) from exc

    data = resp.json()
    return MetaGPTResponse(
        message=data.get("message", "MetaGPT task started"),
        workspace=data.get("workspace"),
    )
