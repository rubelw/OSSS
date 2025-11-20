# src/MetaGPT/metagpt_server.py
from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from MetaGPT.roles_registry import ROLE_REGISTRY, DEFAULT_ROLE_NAME

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)



# Directory where we write per-call MetaGPT logs.
# In docker-compose, mount e.g.: ./logs/metagpt:/logs/metagpt
METAGPT_LOG_DIR = os.getenv("METAGPT_LOG_DIR", "/logs/metagpt")

app = FastAPI()


# --------- Request / Response models ---------

class RunRequest(BaseModel):
    # What the A2A agent sends
    query: str
    role: str | None = None          # e.g. "analyst", "principal"
    rag_index: str | None = None     # optional, for your RAG stack
    workspace: str | None = None     # optional, in case you route by workspace


class RunResponse(BaseModel):
    role: str
    result: dict | list | str | int | float | bool | None


# --------- Logging helper ---------

def log_metagpt_run(
    role: str,
    query: str,
    rag_index: str | None,
    workspace: str | None,
    team_result: object,
) -> None:
    """
    Write a detailed log of a MetaGPT /run call to disk.

    Inside container:
      /logs/metagpt/<timestamp>-<role>.log

    On host (with volume):
      ./logs/metagpt/<timestamp>-<role>.log
    """
    base_dir = Path(METAGPT_LOG_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_role = (role or "unknown").replace("/", "_")
    log_path = base_dir / f"{ts}-{safe_role}.log"

    try:
        with log_path.open("w", encoding="utf-8") as f:
            f.write(f"--- MetaGPT /run ---\n")
            f.write(f"timestamp: {ts}\n")
            f.write(f"role: {role}\n")
            if rag_index:
                f.write(f"rag_index: {rag_index}\n")
            if workspace:
                f.write(f"workspace: {workspace}\n")
            f.write("\nQUERY:\n")
            f.write(query)
            f.write("\n\nTEAM RESULT (as JSON if possible):\n")

            try:
                f.write(json.dumps(team_result, indent=2, ensure_ascii=False))
            except TypeError:
                f.write(repr(team_result))
            f.write("\n")
    except Exception:
        logger.exception("Failed to write MetaGPT /run log to %s", log_path)


# --------- FastAPI lifecycle ---------

@app.on_event("startup")
async def startup_event():
    """
    Instantiate one role object per role name and store in app.state.
    This avoids paying construction cost for each /run.
    """
    instances = {}
    for role_name, RoleCls in ROLE_REGISTRY.items():
        instances[role_name] = RoleCls()
    app.state.role_instances = instances
    logger.info(
        "[MetaGPT sidecar] Startup complete. Roles loaded: %s",
        ", ".join(sorted(ROLE_REGISTRY.keys())),
    )


@app.get("/roles")
async def list_roles():
    """
    Simple discovery endpoint – handy for debugging and for the A2A layer.
    """
    return {"roles": sorted(ROLE_REGISTRY.keys())}


# --------- MAIN /run ENDPOINT ---------

@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest):
    """
    Run a single MetaGPT role with a query, and return its result.

    This is what the A2A agent calls as:

      POST /run
      {
        "query": "...",
        "role": "analyst"
      }
    """
    role_name = req.role or DEFAULT_ROLE_NAME
    instances = app.state.role_instances

    if role_name not in instances:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role_name}")

    agent = instances[role_name]

    logger.info(
        "[MetaGPT sidecar] /run start role=%s rag_index=%r workspace=%r query_preview=%r",
        role_name,
        req.rag_index,
        req.workspace,
        req.query[:200],
    )

    # Call your MetaGPT role. For simple single-role agents, .run(query) is fine.
    result = await agent.run(req.query)

    # Normalize to something FastAPI can JSON-encode
    if not isinstance(result, (str, dict, list, int, float, bool, type(None))):
        result = str(result)

    # Log the full call (prompt + result) to disk
    try:
        log_metagpt_run(
            role=role_name,
            query=req.query,
            rag_index=req.rag_index,
            workspace=req.workspace,
            team_result=result,
        )
    except Exception:
        logger.exception("[MetaGPT sidecar] Failed to log /run call")

    logger.info(
        "[MetaGPT sidecar] /run done role=%s, result_preview=%r",
        role_name,
        str(result)[:200],
    )

    return RunResponse(role=role_name, result=result)
