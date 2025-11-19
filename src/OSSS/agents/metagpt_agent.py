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
    role: str | None = None  # optional



class MetaGptRunResponse(BaseModel):
    message: str
    workspace: str


class TwoAgentConversationRequest(BaseModel):
    prompt: str
    rag_index: str | None = None   # optional: let convo pick an index too


async def _call_sidecar_with_role(req: MetaGptRunRequest, default_role: str) -> dict:
    """
    Low-level client that POSTs to the MetaGPT sidecar /run endpoint.
    """
    url = f"{METAGPT_BASE_URL}/run"

    payload = {
        "requirement": req.requirement,
        "investment": req.investment,
        "workspace": req.workspace,
        "role": default_role,
    }

    if req.rag_index is not None:
        payload["rag_index"] = req.rag_index
    if role is not None:
        payload["role"] = role

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


# -------------------------------------------------------------------
# Existing OSSS agent endpoint
# -------------------------------------------------------------------

@router.post("/osss-agent", response_model=MetaGptRunResponse)
async def run_osss_metagpt_via_sidecar(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    FastAPI endpoint that proxies to the MetaGPT sidecar
    for OSSS-focused work.

    Clients call:
      POST /metagpt/osss-agent
    """
    data = await _call_sidecar_with_role(req, default_role="analyst")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/osss_sidecar",
        ),
    )


# -------------------------------------------------------------------
# NEW: Persona-specific agent endpoints
# -------------------------------------------------------------------

@router.post("/accountability-partner-agent", response_model=MetaGptRunResponse)
async def run_accountability_partner_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for an 'accountability partner' persona.

    Clients call:
      POST /metagpt/accountability-partner-agent
    """
    data = await _call_sidecar_with_role(req, default_role="accountability_partner")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT accountability partner run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/accountability_partner_sidecar",
        ),
    )


@router.post("/parent-agent", response_model=MetaGptRunResponse)
async def run_parent_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for a 'parent' persona.

    Clients call:
      POST /metagpt/parent-agent
    """
    data = await _call_sidecar_with_role(req, default_role="parent")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT parent run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/parent_sidecar",
        ),
    )


@router.post("/student-agent", response_model=MetaGptRunResponse)
async def run_student_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for a 'student' persona.

    Clients call:
      POST /metagpt/student-agent
    """
    data = await _call_sidecar_with_role(req, default_role="student")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT student run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/student_sidecar",
        ),
    )


@router.post("/superintendent-agent", response_model=MetaGptRunResponse)
async def run_superintendent_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for a 'superintendent' persona.

    Clients call:
      POST /metagpt/superintendent-agent
    """
    data = await _call_sidecar_with_role(req, default_role="superintendent")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT superintendent run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/superintendent_sidecar",
        ),
    )


@router.post("/school-board-agent", response_model=MetaGptRunResponse)
async def run_school_board_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for a 'school board' persona.

    Clients call:
      POST /metagpt/school-board-agent
    """
    data = await _call_sidecar_with_role(req, default_role="school_board")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT school board run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/school_board_sidecar",
        ),
    )


@router.post("/principal-agent", response_model=MetaGptRunResponse)
async def run_principal_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for a 'principal' persona.

    Clients call:
      POST /metagpt/principal-agent
    """
    data = await _call_sidecar_with_role(req, default_role="principal")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT principal run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/principal_sidecar",
        ),
    )


@router.post("/teacher-agent", response_model=MetaGptRunResponse)
async def run_teacher_agent(req: MetaGptRunRequest) -> MetaGptRunResponse:
    """
    Endpoint for a 'teacher' persona.

    Clients call:
      POST /metagpt/teacher-agent
    """
    data = await _call_sidecar_with_role(req, default_role="teacher")

    return MetaGptRunResponse(
        message=data.get("message", "MetaGPT teacher run started"),
        workspace=data.get(
            "workspace",
            req.workspace or "./metagpt_workspace/teacher_sidecar",
        ),
    )


# -------------------------------------------------------------------
# Two-agent conversation endpoint (unchanged)
# -------------------------------------------------------------------

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
