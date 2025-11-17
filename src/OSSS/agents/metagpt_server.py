from __future__ import annotations

import asyncio
from fastapi import FastAPI
from pydantic import BaseModel

from OSSS.agents.metagpt_osss_agent import run_osss_metagpt_agent


app = FastAPI(title="OSSS MetaGPT Sidecar")


class RunRequest(BaseModel):
    requirement: str
    investment: float | None = 2.0
    workspace: str | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/run")
async def run_agent(req: RunRequest):
    """
    Fire-and-forget MetaGPT run.

    The heavy MetaGPT logic lives in run_osss_metagpt_agent; this endpoint
    just starts it in the background and returns immediately.
    """
    workspace = req.workspace or "./metagpt_workspace/osss_sidecar"

    asyncio.create_task(
        run_osss_metagpt_agent(
            requirement=req.requirement,
            investment=req.investment or 2.0,
            workspace=workspace,
        )
    )

    return {"message": "MetaGPT run started", "workspace": workspace}
