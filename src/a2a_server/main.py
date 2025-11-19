# src/a2a_server/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- models used by the admin UI ----------

class Agent(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class Run(BaseModel):
    id: str
    agent_id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None

class RunCreate(BaseModel):
    agent_id: str
    input: str

# simple in-memory store so UI isn't empty
AGENTS: list[Agent] = [
    Agent(
        id="two-osss-agents",
        name="Two OSSS Agents (stub)",
        description="Stub agent – later will call MetaGPT team.run()",
    )
]
RUNS: dict[str, Run] = {}

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ---------- ADMIN endpoints used by Next.js dashboard ----------

@app.get("/admin/health")
async def admin_health():
    return {"ok": True, "status": "alive"}

@app.get("/admin/agents", response_model=List[Agent])
async def list_agents():
    return AGENTS

@app.get("/admin/runs")
async def list_runs(limit: int = 50):
    runs = list(RUNS.values())
    runs = sorted(runs, key=lambda r: r.created_at or "", reverse=True)
    return {"runs": runs[:limit]}

@app.get("/admin/runs/{run_id}")
async def get_run(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        return {"error": "run not found"}
    return run

@app.post("/admin/trigger")
async def trigger_run(payload: RunCreate):
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        agent_id=payload.agent_id,
        status="queued",
        created_at=_now_iso(),
        updated_at=_now_iso(),
        input_preview=payload.input[:200],
        output_preview=None,
    )
    RUNS[run_id] = run
    # TODO: enqueue background job that actually calls MetaGPT
    return {"id": run_id, "status": "queued"}

# ---------- health/root ----------

@app.get("/health")
async def bare_health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "A2A server is alive"}

# ---------- endpoint metagpt-server expects ----------

class MetaGPTConversationRequest(BaseModel):
    prompt: str
    rag_index: Optional[str] = None

@app.post("/agents/two-osss-agents/conversation")
async def two_osss_agents_conversation(body: MetaGPTConversationRequest):
    # stub implementation; you can replace later with real MetaGPT call
    return {
        "response": f"[stub from a2a] would run two-osss-agents on: {body.prompt}",
        "rag_index": body.rag_index,
    }
