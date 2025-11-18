# src/OSSS/agents/metagpt_agent.py
from __future__ import annotations

import os
import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


logger = logging.getLogger(__name__)

# Inside docker-compose, the service is "metagpt" on port 8001
METAGPT_BASE_URL = os.getenv("METAGPT_BASE_URL", "http://metagpt:8001")

router = APIRouter(prefix="/metagpt", tags=["ai", "metagpt"])


class MetaGptRunRequest(BaseModel):
    requirement: str
    investment: float = 2.0
    workspace: str | None = None


class MetaGptRunResponse(BaseModel):
    message: str
    workspace: str

class TwoAgentConversationRequest(BaseModel):
    prompt: str

async def _call_sidecar(req: MetaGptRunRequest) -> dict:
    """
    Low-level client that POSTs to the MetaGPT sidecar /run endpoint.
    """
    url = f"{METAGPT_BASE_URL}/run"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                json={
                    "requirement": req.requirement,
                    "investment": req.investment,
                    "workspace": req.workspace,
                },
            )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("MetaGPT sidecar call failed")
        raise HTTPException(
            status_code=503,
            detail=f"MetaGPT sidecar not available: {exc}",
        ) from exc

    return resp.json()


async def run_two_agents_via_sidecar(prompt: str) -> dict:
    url = f"{METAGPT_BASE_URL}/converse"  # e.g. http://metagpt:8001/converse
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json={"prompt": prompt})
        resp.raise_for_status()
        return resp.json()

@router.post("/osss-agent", response_model=MetaGptRunResponse)
async def run_osss_metagpt_via_sidecar(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    FastAPI endpoint that proxies to the MetaGPT sidecar.

    Your Next.js / API clients should call:
      POST /metagpt/osss-agent
    on the main OSSS app (port 8000 / 8081), and this route will
    talk to the metagpt container internally.
    """
    data = await _call_sidecar(req)

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/osss_sidecar",
        ),
    )

@router.post("/agents/talk")
async def agents_talk(req: dict):
    result = await run_two_agents_via_sidecar(req["prompt"])
    return result