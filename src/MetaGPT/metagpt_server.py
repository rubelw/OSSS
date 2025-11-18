"""
MetaGPT FastAPI Sidecar with unified logging
"""

from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from MetaGPT.metagpt_osss_agent import (
    run_osss_metagpt_agent,
    run_two_osss_agents_conversation,
)

# -----------------------------------------------------------
# Logging Setup → /workspace/MetaGPT_workspace/logs/sidecar.log
# -----------------------------------------------------------
LOG_DIR = Path("/workspace/MetaGPT_workspace/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "sidecar.log"

logger = logging.getLogger("metagpt_sidecar")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5_000_000,
    backupCount=5,
)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("🚀 MetaGPT sidecar starting…")

# FastAPI App
app = FastAPI(title="OSSS MetaGPT Sidecar")


class RunRequest(BaseModel):
    requirement: str
    investment: float | None = 2.0
    workspace: str | None = None
    rag_index: str | None = None


class ConverseRequest(BaseModel):
    prompt: str


@app.get("/health")
async def health() -> dict:
    logger.info("Health check OK")
    return {"status": "ok"}


@app.post("/run")
async def run_agent(req: RunRequest):
    logger.info(f"🔥 /run called requirement={req.requirement} rag_index={req.rag_index}")

    workspace = req.workspace or "/workspace/MetaGPT_workspace/osss_sidecar"

    asyncio.create_task(
        run_osss_metagpt_agent(
            requirement=req.requirement,
            investment=req.investment or 2.0,
            workspace=workspace,
            rag_index=req.rag_index,
        )
    )

    return {"message": "MetaGPT run started", "workspace": workspace}


@app.post("/converse")
async def converse(req: ConverseRequest):
    logger.info(f"🤖 Two-agent conversation started prompt={req.prompt}")

    result = await run_two_osss_agents_conversation(req.prompt)

    logger.info(f"🤖 Two-agent conversation result={result}")

    return result
