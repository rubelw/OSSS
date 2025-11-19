# src/a2a_server/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from a2a_server.orchestrator import orchestrator  # local orchestrator

app = FastAPI()

# ---- CORS (for Next.js admin UI on 3000) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Request models ----

class TriggerPayload(BaseModel):
    agent_id: str
    input: str


# ---- ADMIN API -----

@app.get("/admin/health")
async def admin_health():
    return {"ok": True, "status": "orchestrator loaded"}


@app.get("/admin/agents")
async def list_agents():
    return orchestrator.list_agents()


@app.get("/admin/runs")
async def list_runs(limit: int = 50):
    return orchestrator.list_runs(limit=limit)


@app.post("/admin/trigger")
async def trigger(payload: TriggerPayload):
    """
    Triggers an A2A-backed MetaGPT agent.

    - Creates a Run
    - Calls the A2A agent (python-a2a) via orchestrator.run_agent(...)
    - Returns the updated Run record
    """
    if not payload.agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    if not payload.input.strip():
        raise HTTPException(status_code=400, detail="input is required")

    # Important: orchestrator.run_agent is async now, so we MUST await it.
    run = await orchestrator.run_agent(payload.agent_id, payload.input)
    return run


@app.get("/admin/runs/{run_id}")
async def get_run(run_id: str):
    run = orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ---- Simple health/debug endpoints ----

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "A2A server is alive!!!"}
