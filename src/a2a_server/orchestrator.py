# src/a2a_server/orchestrator.py

from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from python_a2a import A2AClient


@dataclass
class Agent:
    id: str
    name: str
    description: Optional[str] = None


@dataclass
class Run:
    id: str
    agent_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None


class InMemoryOrchestrator:
    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}
        self._runs: Dict[str, Run] = {}

    # ---------- A2A CLIENT CALL ----------

    def _call_a2a_agent(self, text: str, skill: Optional[str] = None) -> str:
        """
        Call the MetaGPT A2A agent (python-a2a server) and return its text result.

        Since A2AClient.ask(...) in your version does NOT accept a `skill` kwarg,
        we encode the desired skill into the text as a simple header:

            [role:analyst]
            actual user text...

        MetaGPTA2AAgent can then parse this header to decide which MetaGPT role to use.
        """
        client = A2AClient("http://a2a-agent:9000")  # service name from docker-compose

        decorated_text = text
        if skill:
            decorated_text = f"[role:{skill}]\n{text}"

        result = client.ask(decorated_text)
        return result

    # ---------- AGENT REGISTRATION ----------

    def register_agent(self, id: str, name: str, description: Optional[str] = None) -> None:
        """Register or overwrite an agent definition."""
        self._agents[id] = Agent(id=id, name=name, description=description)

    # ---------- AGENTS ----------

    def list_agents(self) -> List[dict]:
        return [asdict(a) for a in self._agents.values()]

    # ---------- RUNS ----------

    def list_runs(self, limit: int = 50) -> dict:
        runs_sorted = sorted(
            self._runs.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return {"runs": [self._run_to_dict(r) for r in runs_sorted[:limit]]}

    def get_run(self, run_id: str) -> dict:
        run = self._runs.get(run_id)
        if not run:
            return {"error": "run_not_found", "id": run_id}
        return self._run_to_dict(run)

    async def run_agent(
        self,
        agent_id: str,
        input_text: str,
        skill: Optional[str] = None,
    ) -> dict:
        """
        Create a Run and actually execute it by calling the A2A agent.

        - Validates agent_id
        - Creates a Run with status 'running'
        - Calls the MetaGPT A2A agent via python-a2a
        - Updates Run with 'succeeded' or 'failed' and an output_preview
        """
        if agent_id not in self._agents:
            return {"error": "unknown_agent", "agent_id": agent_id}

        now = datetime.now(timezone.utc)
        run_id = str(uuid.uuid4())

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

        try:
            # Call the A2A agent and capture its output
            output_text = self._call_a2a_agent(input_text, skill=skill)

            run.status = "succeeded"
            run.updated_at = datetime.now(timezone.utc)
            run.output_preview = (output_text[:200] if output_text else None)
            self._runs[run_id] = run
        except Exception as e:
            err_text = f"Error calling A2A agent: {e}"
            run.status = "failed"
            run.updated_at = datetime.now(timezone.utc)
            run.output_preview = err_text[:200]
            self._runs[run_id] = run

        return self._run_to_dict(run)

    def _run_to_dict(self, run: Run) -> dict:
        return {
            "id": run.id,
            "agent_id": run.agent_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "input_preview": run.input_preview,
            "output_preview": run.output_preview,
        }


# Global orchestrator instance that main.py imports
orchestrator = InMemoryOrchestrator()

# Register the real MetaGPT A2A-backed agent
orchestrator.register_agent(
    id="metagpt-a2a",
    name="MetaGPT A2A Agent",
    description="Backed by python-a2a + MetaGPT roles via a2a_agent.py",
)
