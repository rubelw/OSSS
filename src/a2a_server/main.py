# src/a2a_server/main.py
"""
Main FastAPI application for the A2A Orchestrator service.

This service exposes:
    - Admin API endpoints (used by your Next.js dashboard)
    - Health checks for Docker / monitoring
    - Trigger endpoint to create new agent runs
    - Read-only access to run history

This service *does not* execute any AI models itself.
It delegates all actual work to the Orchestrator, which then delegates to the
python-a2a agent ("a2a-agent" container) which finally calls MetaGPT.

Flow:
    UI -> this FastAPI -> Orchestrator -> A2A Agent -> MetaGPT

The Orchestrator holds state in memory; this API simply provides HTTP access.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the global orchestrator instance (created in orchestrator.py)
# We do not create a new one here — we use the shared module-level one.
from a2a_server.orchestrator import orchestrator


# --------------------------------------------------------------------
# FastAPI Application Setup
# --------------------------------------------------------------------

app = FastAPI(
    title="A2A Orchestrator API",
    description="Admin/Control API for triggering A2A-backed MetaGPT runs.",
    version="0.1.0",
)

# --------------------------------------------------------------------
# CORS Configuration
# --------------------------------------------------------------------
# Allow connections from your Next.js admin panel (running on port 3000).
# This enables browser requests from http://localhost:3000 to call your A2A API.
#
# If you later deploy the admin UI to a real domain,
# update this allow_origins list appropriately.
# --------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",     # Local Next.js dev server
        "http://127.0.0.1:3000",     # Alternate access
        # Add production URL(s) here when needed
    ],
    allow_credentials=False,
    allow_methods=["*"],            # Allow GET, POST, etc.
    allow_headers=["*"],            # Allow JSON, Authorization, etc.
)


# --------------------------------------------------------------------
# Request Models
# --------------------------------------------------------------------
class ParentStudentCheckinPayload(BaseModel):
    grades_text: str
    # NEW: allow overriding which student agent & skill to use
    student_agent_id: str | None = "student-agent"
    student_skill: str | None = "student"
    # You can also make teacher overridable later if you want:
    # teacher_agent_id: str | None = "teacher-agent"
    # teacher_skill: str | None = "teacher"


class TriggerPayload(BaseModel):
    """
    The expected JSON body for POST /admin/trigger.

    Example:
        {
            "agent_id": "metagpt-a2a",
            "input": "Summarize this text...",
            "skill": "analyst"
        }

    `skill` is optional; if omitted, orchestrator defaults to "analyst".
    """
    agent_id: str
    input: str
    skill: str | None = None


# --------------------------------------------------------------------
# ADMIN API ENDPOINTS (used by the dashboard)
# --------------------------------------------------------------------
# The UI ONLY calls endpoints under /admin/*
# --------------------------------------------------------------------

@app.get("/admin/health")
async def admin_health():
    """
    Simple endpoint used by the admin dashboard to confirm that:
    - This FastAPI server is running
    - The orchestrator module loaded successfully

    Does NOT check A2A agent or MetaGPT — only local health.
    """
    return {"ok": True, "status": "orchestrator loaded"}


@app.get("/admin/agents")
async def list_agents():
    """
    Return all registered agents.

    The admin UI uses this to populate the "Agents" sidebar and
    the dropdown list inside the "Trigger new run" panel.
    """
    return orchestrator.list_agents()


@app.get("/admin/runs")
async def list_runs(limit: int = 50):
    """
    Return the N most recent runs (default = 50).

    Used to populate the "Recent Runs" table.
    """
    return orchestrator.list_runs(limit=limit)


@app.post("/admin/trigger")
async def trigger(payload: TriggerPayload):
    """
    Trigger a new run of an A2A-backed agent.

    This is the MOST important endpoint for your admin dashboard.

    Workflow:
        1. Validate the request payload
        2. Create a new Run record with status="running"
        3. Send the text (and chosen skill) to the Orchestrator
        4. Orchestrator forwards the request to the python-a2a agent
        5. python-a2a calls MetaGPT
        6. Orchestrator updates the run result
        7. Return final Run JSON to the client

    This endpoint is synchronous: the dashboard will get back a completed run.
    """

    # --- Validate inputs ---
    if not payload.agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    if not payload.input.strip():
        raise HTTPException(status_code=400, detail="input is required")

    # --- Execute run via orchestrator ---
    run = await orchestrator.run_agent(
        agent_id=payload.agent_id,
        input_text=payload.input,
        skill=payload.skill,
    )

    return run


@app.get("/admin/runs/{run_id}")
async def get_run(run_id: str):
    """
    Fetch a single run by ID.

    Used by the dashboard's "Run detail" drawer UI.
    """

    run = orchestrator.get_run(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run


@app.post("/admin/parent-student-checkin")
async def parent_student_checkin(payload: ParentStudentCheckinPayload):
    """
    Orchestrate a simple parent→student interaction about grades:

      1) Use the parent-agent to draft a question to the student.
      2) Use the (configurable) student-agent to answer that question as the student.
      3) Orchestrator may optionally involve teacher-agent based on the student's response.

    Body example:
      {
        "grades_text": "Math: B-, English: A, Science: C+, ...",
        "student_agent_id": "angry-student-agent",
        "student_skill": "angry_student"
      }
    """
    result = await orchestrator.parent_student_grade_checkin(
        grades_text=payload.grades_text,
        student_agent_id=payload.student_agent_id or "student-agent",
        student_skill=payload.student_skill or "student",
        # if/when you expose teacher overrides on the payload, pass them here too
        # teacher_agent_id=payload.teacher_agent_id or "teacher-agent",
        # teacher_skill=payload.teacher_skill or "teacher",
    )
    return result


# --------------------------------------------------------------------
# Public / Debug / Dev Endpoints
# --------------------------------------------------------------------

@app.get("/health")
async def health():
    """
    A general-purpose health endpoint.

    Unlike /admin/health, this can be used by Docker, k8s, load balancers, etc.
    """
    return {"status": "ok"}


@app.get("/")
async def root():
    """
    Friendly greeting for browser testing.
    """
    return {"message": "A2A server is alive!!!"}
