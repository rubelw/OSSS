# src/a2a_server/orchestrator.py

"""
The Orchestrator sits between your UI (admin dashboard) and your A2A Agent.

Responsibilities:
- Register available agents (in-memory for now)
- Accept trigger/run requests from the admin UI
- Forward the user's prompt to the python-a2a agent ("a2a-agent")
- Track run history, including input/output previews
- Store run state in memory (ephemeral — good for dev/demo)

This implementation is intentionally simple and easy to replace later with:
- A real database (PostgreSQL)
- Background task runners
- Multi-agent pipelines
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from python_a2a import A2AClient


# -------------------------------------------------------------------
# Data Models: Agent + Run (in-memory)
# -------------------------------------------------------------------

@dataclass
class Agent:
    """
    Represents one logical agent the orchestrator can invoke.

    Example:
        id="metagpt-a2a"
        name="MetaGPT Multi-Role Agent"
        description="Backed by python-a2a and a2a_agent.py"
    """
    id: str
    name: str
    description: Optional[str] = None


@dataclass
class Run:
    """
    Represents a single execution of an agent:
    - Unique run ID
    - Which agent executed it
    - Status (running, succeeded, failed)
    - Timestamps
    - Input + output previews (for admin UI display)
    """
    id: str
    agent_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None


# -------------------------------------------------------------------
# In-Memory Orchestrator
# -------------------------------------------------------------------

class InMemoryOrchestrator:
    """
    The core orchestration engine.

    Current responsibilities:
      - Register agents
      - Trigger new runs
      - Call A2A agent (python-a2a server)
      - Track runs in-memory
      - Present runs + agents to the admin dashboard

    This version keeps everything ephemeral in RAM; restarting the container
    clears all run history — intentionally simple for development.
    """

    def __init__(self) -> None:
        # All agents registered with the system (key = agent_id)
        self._agents: Dict[str, Agent] = {}

        # All runs keyed by run_id (simple in-memory log)
        self._runs: Dict[str, Run] = {}

    # -------------------------------------------------------------------
    # A2A CLIENT CALL — ACTUAL AGENT EXECUTION
    # -------------------------------------------------------------------

    def _call_a2a_agent(self, text: str, skill: Optional[str] = None) -> str:
        """
        Core integration point with python-a2a.

        Your python-a2a SDK **does not support** passing `skill=<name>` directly
        as an argument to `A2AClient.ask(...)`.

        To work around this limitation, the orchestrator embeds the skill
        directly *into the text payload* using a simple header:

            [role:data_interpreter]
            Please summarize this CSV…

        Your a2a_agent.py is responsible for:
        - Detecting the header inside message.content.text
        - Choosing the correct MetaGPT role based on it
        - Stripping the header before sending text to MetaGPT

        This keeps the UI clean and gives explicit multi-role control.
        """

        # Address of python-a2a HTTP server (inside docker-compose network)
        client = A2AClient("http://a2a-agent:9000")

        # If a skill is selected (analyst, data_interpreter), prepend it as a header
        decorated_text = text
        if skill:
            decorated_text = f"[role:{skill}]\n{text}"

        # Call the A2A agent synchronously (blocking)
        result = client.ask(decorated_text)
        return result

    # -------------------------------------------------------------------
    # AGENT REGISTRATION
    # -------------------------------------------------------------------

    def register_agent(self, id: str, name: str, description: Optional[str] = None) -> None:
        """
        Register a logical agent in the orchestrator.

        The admin UI reads this list to show selectable agents.
        """
        self._agents[id] = Agent(id=id, name=name, description=description)

    # -------------------------------------------------------------------
    # AGENTS LISTING
    # -------------------------------------------------------------------

    def list_agents(self) -> List[dict]:
        """
        Return a serializable list of all registered agents.
        Used by the admin dashboard's "Agents" panel.
        """
        return [asdict(a) for a in self._agents.values()]

    # -------------------------------------------------------------------
    # RUN LISTING & LOOKUP
    # -------------------------------------------------------------------

    def list_runs(self, limit: int = 50) -> dict:
        """
        Return the most recent N runs, newest first.

        Used by the admin UI "Recent runs" table.
        """
        runs_sorted = sorted(
            self._runs.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return {"runs": [self._run_to_dict(r) for r in runs_sorted[:limit]]}

    def get_run(self, run_id: str) -> dict:
        """
        Retrieve a single run (for the detail drawer).
        """
        run = self._runs.get(run_id)
        if not run:
            return {"error": "run_not_found", "id": run_id}
        return self._run_to_dict(run)

    # -------------------------------------------------------------------
    # RUN EXECUTION (triggered by POST /admin/trigger)
    # -------------------------------------------------------------------

    async def run_agent(
        self,
        agent_id: str,
        input_text: str,
        skill: Optional[str] = None,
    ) -> dict:
        """
        Execute a new run of the selected agent.

        Workflow:
          1. Validate the agent ID exists
          2. Create a new Run object (status="running")
          3. Call the A2A agent to get a result
          4. Update the Run status (succeeded/failed)
          5. Return serialized Run for the dashboard
        """

        # --- (1) Validate agent existence ---
        if agent_id not in self._agents:
            return {"error": "unknown_agent", "agent_id": agent_id}

        now = datetime.now(timezone.utc)
        run_id = str(uuid.uuid4())

        # --- (2) Create the run record ---
        run = Run(
            id=run_id,
            agent_id=agent_id,
            status="running",
            created_at=now,
            updated_at=now,
            input_preview=(input_text[:200] if input_text else None),
            output_preview=None,
        )
        self._runs[run_id] = run

        # --- (3) Execute the run by calling python-a2a ---
        try:
            output_text = self._call_a2a_agent(input_text, skill=skill)

            # --- (4a) Success path ---
            run.status = "succeeded"
            run.updated_at = datetime.now(timezone.utc)
            run.output_preview = (output_text[:200] if output_text else None)
            self._runs[run_id] = run

        except Exception as e:
            # --- (4b) Failure path ---
            err_text = f"Error calling A2A agent: {e}"
            run.status = "failed"
            run.updated_at = datetime.now(timezone.utc)
            run.output_preview = err_text[:200]
            self._runs[run_id] = run

        # --- (5) Return the final run record ---
        return self._run_to_dict(run)

    # -------------------------------------------------------------------
    # RUN SERIALIZATION
    # -------------------------------------------------------------------

    def _run_to_dict(self, run: Run) -> dict:
        """
        Convert a Run dataclass into a JSON-serializable dictionary.

        Ensures datetime fields are ISO strings so the front-end can parse them cleanly.
        """
        return {
            "id": run.id,
            "agent_id": run.agent_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "input_preview": run.input_preview,
            "output_preview": run.output_preview,
        }


# -------------------------------------------------------------------
# GLOBAL ORCHESTRATOR INSTANCE
# (Imported directly by main.py)
# -------------------------------------------------------------------

orchestrator = InMemoryOrchestrator()

# Register the real MetaGPT A2A-backed agent at startup
orchestrator.register_agent(
    id="metagpt-a2a",
    name="MetaGPT A2A Agent",
    description="Backed by python-a2a + MetaGPT roles via a2a_agent.py",
)
