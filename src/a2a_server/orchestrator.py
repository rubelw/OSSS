# src/a2a_server/orchestrator.py

"""
The Orchestrator sits between your UI (admin dashboard) and your A2A Agent.

Responsibilities:
- Register available agents (in-memory for now)
- Accept trigger/run requests from the admin UI
- Forward the user's prompt to the python-a2a agent ("a2a-agent")
- Track run history, including input/output previews
- Store run state in memory (ephemeral — good for dev/demo)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
from pathlib import Path
import logging
import os

from python_a2a import A2AClient

# Which logical agents should have their runs logged to disk
LOGGED_AGENTS = {
    "parent-agent",
    "student-agent",
    "teacher-agent",
    "angry-student-agent",
    # add "principal-agent", etc. if you want
}

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Data Models: Agent + Run (in-memory)
# -------------------------------------------------------------------

@dataclass
class Agent:
    """
    Represents one logical agent the orchestrator can invoke.
    """
    id: str
    name: str
    description: Optional[str] = None
    # optional default skill for this agent (maps to MetaGPT role)
    default_skill: Optional[str] = None


@dataclass
class Run:
    """
    Represents a single execution of an agent.
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
    def __init__(self) -> None:
        # All agents registered with the system (key = agent_id)
        self._agents: Dict[str, Agent] = {}
        # All runs keyed by run_id (simple in-memory log)
        self._runs: Dict[str, Run] = {}

        # Allow overriding A2A agent URL via env
        self._a2a_url = os.getenv("A2A_AGENT_URL", "http://a2a-agent:9000")
        logger.info("InMemoryOrchestrator using A2A agent URL: %s", self._a2a_url)

    # -------------------------------------------------------------------
    # A2A CLIENT CALL — ACTUAL AGENT EXECUTION
    # -------------------------------------------------------------------

    def _call_a2a_agent(self, text: str, skill: Optional[str] = None) -> str:
        """
        Core integration point with python-a2a.

        We embed the skill directly into the text payload as a header:

            [role:student]
            actual user text...

        a2a_agent.py parses that header and chooses the MetaGPT role.
        """
        client = A2AClient(self._a2a_url)

        decorated_text = text
        if skill:
            decorated_text = f"[role:{skill}]\n{text}"

        logger.info(
            "Calling a2a-agent at %s with skill=%r, text_preview=%r",
            self._a2a_url,
            skill,
            decorated_text[:120],
        )
        result = client.ask(decorated_text)
        return result

    # -------------------------------------------------------------------
    # AGENT REGISTRATION
    # -------------------------------------------------------------------

    def register_agent(
        self,
        id: str,
        name: str,
        description: Optional[str] = None,
        default_skill: Optional[str] = None,
    ) -> None:
        """
        Register a logical agent in the orchestrator.
        """
        self._agents[id] = Agent(
            id=id,
            name=name,
            description=description,
            default_skill=default_skill,
        )

    # -------------------------------------------------------------------
    # AGENTS LISTING
    # -------------------------------------------------------------------

    def list_agents(self) -> List[dict]:
        """
        Return a serializable list of all registered agents.
        """
        return [asdict(a) for a in self._agents.values()]

    # -------------------------------------------------------------------
    # RUN LISTING & LOOKUP
    # -------------------------------------------------------------------

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
        """

        # --- (1) Validate agent existence ---
        agent = self._agents.get(agent_id)
        if not agent:
            return {"error": "unknown_agent", "agent_id": agent_id}

        # If no explicit skill was passed, use the agent's default.
        effective_skill = skill or agent.default_skill

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
            output_text = self._call_a2a_agent(input_text, skill=effective_skill)

            run.status = "succeeded"
            run.updated_at = datetime.now(timezone.utc)
            run.output_preview = (output_text[:200] if output_text else None)
            self._runs[run_id] = run

            # --- (4) Optional per-run logging for specific agents ---
            if agent_id in LOGGED_AGENTS:
                self._log_agent_run(
                    agent_id=agent_id,
                    run_id=run_id,
                    skill=effective_skill,
                    input_text=input_text,
                    output_text=output_text,
                )

        except Exception as e:
            err_text = f"Error calling A2A agent: {e}"
            run.status = "failed"
            run.updated_at = datetime.now(timezone.utc)
            run.output_preview = err_text[:200]
            self._runs[run_id] = run

            if agent_id in LOGGED_AGENTS:
                # IMPORTANT: use err_text here, not output_text
                self._log_agent_run(
                    agent_id=agent_id,
                    run_id=run_id,
                    skill=effective_skill,
                    input_text=input_text,
                    output_text=err_text,
                )

        return self._run_to_dict(run)

    # -------------------------------------------------------------------
    # PER-RUN FILE LOGGING (GENERIC BY AGENT)
    # -------------------------------------------------------------------

    def _log_agent_run(
        self,
        agent_id: str,
        run_id: str,
        skill: Optional[str],
        input_text: str,
        output_text: str,
    ) -> None:
        """
        Write a per-run log file for a given logical agent.

        Inside the container:
          /logs/<agent_id>/<run_id>.log

        On the host (with volume mapping):
          ./logs/a2a/<agent_id>/<run_id>.log
        """
        base_dir = Path("/logs") / agent_id
        base_dir.mkdir(parents=True, exist_ok=True)

        log_path = base_dir / f"{run_id}.log"

        timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Writing agent run log: agent_id=%s run_id=%s path=%s",
            agent_id,
            run_id,
            log_path,
        )

        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"--- Agent Run {run_id} ---\n")
            f.write(f"timestamp: {timestamp}\n")
            f.write(f"agent_id: {agent_id}\n")
            if skill:
                f.write(f"skill: {skill}\n")
            f.write("\nINPUT:\n")
            f.write(input_text)
            f.write("\n\nOUTPUT:\n")
            f.write(output_text)
            f.write("\n\n")

    # -------------------------------------------------------------------
    # RUN SERIALIZATION
    # -------------------------------------------------------------------

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

    # -------------------------------------------------------------------
    # PARENT → STUDENT → (OPTIONAL) TEACHER CHECK-IN WORKFLOW
    # -------------------------------------------------------------------

    async def parent_student_grade_checkin(
        self,
        grades_text: str,
        parent_agent_id: str = "parent-agent",
        student_agent_id: str = "student-agent",
        teacher_agent_id: Optional[str] = "teacher-agent",
        parent_skill: Optional[str] = "parent",
        student_skill: Optional[str] = "student",
        teacher_skill: Optional[str] = "teacher",
    ) -> dict:
        """
        1) parent-agent drafts a question to the student about grades
        2) (configurable) student-agent responds as the student
        3) IF the student:
             - mentions talking to a teacher, OR
             - shows concerning / dismissive / risky attitudes
           THEN teacher-agent drafts a short, supportive response.

        Returns:
          {
            "parent_run": {...},
            "student_run": {...},
            "parent_question": "<string>",
            "student_full_answer": "<string>",
            "teacher_run": {...} | None,
          }
        """

        # ---- 1) Parent drafts the question ----
        parent_prompt = (
            "You are a caring, constructive parent.\n\n"
            "Below is a description of the student's current grades.\n"
            "Write a single, clear question you would ask the student "
            "to understand how they feel about their grades and what support they need.\n\n"
            f"GRADES:\n{grades_text}\n"
        )

        parent_run = await self.run_agent(
            agent_id=parent_agent_id,
            input_text=parent_prompt,
            skill=parent_skill,
        )

        parent_question = parent_run.get("output_preview") or ""

        # ---- 2) Student responds to the parent's question ----
        student_prompt = (
            "You are the student responding honestly and respectfully to your parent.\n\n"
            "Your parent asks you this question about your grades:\n\n"
            f"\"{parent_question}\"\n\n"
            "Reply in your own words, explaining how you feel about your grades,\n"
            "what challenges you're facing, and what help or next steps would be useful."
        )

        student_run = await self.run_agent(
            agent_id=student_agent_id,
            input_text=student_prompt,
            skill=student_skill,
        )

        # Full (untruncated) answer via direct A2A call
        try:
            student_full_answer = self._call_a2a_agent(
                text=student_prompt,
                skill=student_skill,
            )
        except Exception as e:
            logger.exception(
                "parent_student_grade_checkin: failed to get full student answer"
            )
            student_full_answer = f"(Error retrieving full student response: {e})"

        # ---- 3) Decide whether to involve the teacher-agent ----
        teacher_run: Optional[dict] = None
        lowered = (student_full_answer or "").lower()

        teacher_ref_phrases = [
            " teacher",
            "teacher ",
            "talk to my teacher",
            "talk to the teacher",
            "talk to my science teacher",
            "mrs.",
            "mr.",
        ]
        wants_teacher_help = any(phrase in lowered for phrase in teacher_ref_phrases)

        concerning_phrases = [
            "not really worried about my grades",
            "i'm not really worried about my grades",
            "not a big deal",
            "i don't really care about my grades",
            "i don’t really care about my grades",
            "skip school",
            "skipping school",
            "road trip with my friends",
            "tell my teacher i'm sick",
            "tell my teacher im sick",
            "she'll never know",
            "she will never know",
            "they'll never know",
            "they will never know",
            "i'll just lie",
            "i will just lie",
        ]
        concerning_attitude = any(p in lowered for p in concerning_phrases)

        should_call_teacher = (
            teacher_agent_id is not None and (wants_teacher_help or concerning_attitude)
        )

        if should_call_teacher:
            reasons = []
            if wants_teacher_help:
                reasons.append("the student explicitly mentioned talking to a teacher")
            if concerning_attitude:
                reasons.append(
                    "the student expressed a dismissive or risky attitude about "
                    "grades, attendance, or honesty"
                )
            reasons_text = "; ".join(reasons) if reasons else "general concern."

            teacher_prompt = (
                "You are the student's teacher in the Dallas Center-Grimes (DCG) Community School District.\n\n"
                "A parent and student just had the following exchange about the student's grades.\n\n"
                f"GRADES:\n{grades_text}\n\n"
                f"PARENT QUESTION:\n{parent_question}\n\n"
                f"STUDENT RESPONSE:\n{student_full_answer}\n\n"
                f"Context for why you're being looped in: {reasons_text}\n\n"
                "Write a short, supportive message you would provide as the teacher. "
                "Your message should:\n"
                "- Acknowledge the student's feelings and current mindset.\n"
                "- Address any dismissive or risky attitudes (e.g., skipping school, not caring, lying) calmly but clearly.\n"
                "- Offer concrete support options (office hours, extra help, makeup work, clearer expectations).\n"
                "- Suggest specific next steps for the student and how you’ll partner with the parent.\n"
            )

            teacher_run = await self.run_agent(
                agent_id=teacher_agent_id,
                input_text=teacher_prompt,
                skill=teacher_skill,
            )

        return {
            "parent_run": parent_run,
            "student_run": student_run,
            "parent_question": parent_question,
            "student_full_answer": student_full_answer,
            "teacher_run": teacher_run,
        }

# -------------------------------------------------------------------
# GLOBAL ORCHESTRATOR INSTANCE
# -------------------------------------------------------------------

orchestrator = InMemoryOrchestrator()

# Base MetaGPT A2A-backed agent (generic)
orchestrator.register_agent(
    id="metagpt-a2a",
    name="MetaGPT A2A Agent",
    description="Backed by python-a2a + MetaGPT roles via a2a_agent.py",
    default_skill="analyst",
)

# Principal-focused logical agent
orchestrator.register_agent(
    id="principal-agent",
    name="Principal Agent",
    description="School principal persona (email, announcements, discipline, etc).",
    default_skill="principal",
)

# Teacher-focused logical agent
orchestrator.register_agent(
    id="teacher-agent",
    name="Teacher Agent",
    description="Teacher-facing drafting, classroom communication, and planning.",
    default_skill="teacher",
)

# Student-focused logical agent
orchestrator.register_agent(
    id="student-agent",
    name="Student Agent",
    description="Student persona: questions, reflections, and planning.",
    default_skill="student",
)

# Angry Student-focused logical agent
orchestrator.register_agent(
    id="angry-student-agent",
    name="Angry Student Agent",
    description="Angry Student persona: questions, reflections, and planning.",
    default_skill="angry_student",
)


# Parent-focused logical agent
orchestrator.register_agent(
    id="parent-agent",
    name="Parent Agent",
    description="Parent voice and communication support.",
    default_skill="parent",
)

# Superintendent-focused logical agent
orchestrator.register_agent(
    id="superintendent-agent",
    name="Superintendent Agent",
    description="District-level communications and strategy reflections.",
    default_skill="superintendent",
)

# School board-focused logical agent
orchestrator.register_agent(
    id="school-board-agent",
    name="School Board Agent",
    description="Board meeting prep, resolutions, and community messages.",
    default_skill="school_board",
)

# Accountability partner logical agent
orchestrator.register_agent(
    id="accountability-partner-agent",
    name="Accountability Partner Agent",
    description="Helps set goals and follow-through steps as an accountability partner.",
    default_skill="accountability_partner",
)
