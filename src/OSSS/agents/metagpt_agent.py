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
    rag_index: str | None = None   # <-- forwarded to sidecar


class MetaGptRunResponse(BaseModel):
    message: str
    workspace: str


class TwoAgentConversationRequest(BaseModel):
    prompt: str
    rag_index: str | None = None   # optional: let convo pick an index too


async def _call_sidecar(req: MetaGptRunRequest) -> dict:
    """
    Low-level client that POSTs to the MetaGPT sidecar /run endpoint.
    """
    url = f"{METAGPT_BASE_URL}/run"

    payload: dict = {
        "requirement": req.requirement,
        "investment": req.investment,
        "workspace": req.workspace,
    }
    if req.rag_index is not None:
        payload["rag_index"] = req.rag_index

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("MetaGPT sidecar call failed")
        raise HTTPException(
            status_code=503,
            detail=f"MetaGPT sidecar not available: {exc}",
        ) from exc

    return resp.json()


async def run_two_agents_via_sidecar(
    prompt: str,
    rag_index: str | None = None,
) -> dict:
    """
    Call the MetaGPT sidecar /converse endpoint for a two-agent conversation.
    """
    url = f"{METAGPT_BASE_URL}/converse"

    payload: dict = {"prompt": prompt}
    if rag_index is not None:
        payload["rag_index"] = rag_index

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("MetaGPT two-agent conversation failed")
        raise HTTPException(
            status_code=503,
            detail=f"MetaGPT sidecar (two agents) not available: {exc}",
        ) from exc

    return resp.json()


@router.post("/osss-agent", response_model=MetaGptRunResponse)
async def run_osss_metagpt_via_sidecar(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    FastAPI endpoint that proxies to the MetaGPT sidecar.

    Your Next.js / API clients should call:
      POST /metagpt/osss-agent

    This route will talk to the metagpt container internally.
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
async def agents_talk(req: TwoAgentConversationRequest):
    """
    Start a two-agent conversation via the MetaGPT sidecar.

    Body example:
      {
        "prompt": "Discuss cafeteria scheduling strategies",
        "rag_index": "main"
      }
    """
    result = await run_two_agents_via_sidecar(
        prompt=req.prompt,
        rag_index=req.rag_index,
    )
    return result
