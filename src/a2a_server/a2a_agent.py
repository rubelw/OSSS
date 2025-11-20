"""
MetaGPT-backed A2A Agent

This module defines a python-a2a Agent that *wraps* your MetaGPT FastAPI
sidecar and exposes it over the A2A protocol.

Overall flow:

  A2A Client (orchestrator)  -->  this Agent (python-a2a)  -->  MetaGPT HTTP sidecar

1. The orchestrator sends a Task (with text + optional [role:...] header).
2. python-a2a calls `MetaGPTA2AAgent.handle_task(task)`.
3. We decide which MetaGPT role to use (analyst, parent, student, etc.).
4. We call MetaGPT's /run endpoint with {query, role}.
5. We wrap MetaGPT's result in A2A artifacts and mark the task COMPLETED.
"""

import os
import logging
from typing import Any, Dict, Tuple
import json
from datetime import datetime, timezone
from pathlib import Path
import re

import httpx
from python_a2a import (
    A2AServer,
    TaskStatus,
    TaskState,
    AgentCard,
    AgentSkill,
    run_server,
)

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------

# Where the MetaGPT FastAPI sidecar is reachable *from this container*.
METAGPT_BASE_URL = os.getenv("METAGPT_BASE_URL", "http://metagpt:8001")

# Supported MetaGPT roles that this A2A agent knows how to *advertise*.
# We won't restrict to this list when actually calling MetaGPT.
SUPPORTED_ROLES = [
    "analyst",
    "principal",
    "principal_email",
    "principal_discipline",
    "principal_announcement",
    "teacher",
    "student",
    "parent",
    "superintendent",
    "school_board",
    "accountability_partner",
]

# Directory to write per-call logs for this A2A agent.
A2A_AGENT_LOG_DIR = os.getenv("A2A_AGENT_LOG_DIR", "/logs/a2a-agent")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ROLE_HEADER_RE = re.compile(r"^\[role:(?P<role>[a-zA-Z0-9_\-]+)\]\s*$")


# --------------------------------------------------------------------
# Agent implementation
# --------------------------------------------------------------------

class MetaGPTA2AAgent(A2AServer):
    """
    A python-a2a Agent that proxies tasks to a MetaGPT sidecar.
    """

    def __init__(self) -> None:
        card = AgentCard(
            name="MetaGPT Multi-Role Agent",
            description=(
                "Wraps multiple MetaGPT roles (analyst, principal, parent, student, etc.) "
                "and exposes them over the A2A protocol."
            ),
            url="http://a2a-agent:9000",
            version="0.1.0",
            skills=[
                AgentSkill(
                    name="analyst",
                    description="Use MetaGPT's analyst role for structured analysis.",
                    tags=["metagpt", "analysis"],
                    examples=["Analyze the local economic impact of AI adoption."],
                ),
                AgentSkill(
                    name="principal",
                    description="Generalist school principal: parent communication, staff notes, operations.",
                    tags=["metagpt", "education", "principal"],
                    examples=["Draft a message to staff about a new schedule policy."],
                ),
                AgentSkill(
                    name="principal_email",
                    description="Specialized in writing principal emails to parents and staff.",
                    tags=["metagpt", "education", "principal", "email"],
                    examples=["Write an email to parents about early dismissal due to weather."],
                ),
                AgentSkill(
                    name="principal_discipline",
                    description="Reason about student behavior and discipline situations as a principal.",
                    tags=["metagpt", "education", "principal", "discipline"],
                    examples=["Help write a note home about a behavior incident in class."],
                ),
                AgentSkill(
                    name="principal_announcement",
                    description="Write public-facing announcements and newsletters.",
                    tags=["metagpt", "education", "principal", "announcement"],
                    examples=["Draft a weekly principal newsletter for families."],
                ),
                AgentSkill(
                    name="teacher",
                    description="Teacher-facing drafting, classroom communication, and planning.",
                    tags=["metagpt", "education", "teacher"],
                    examples=["Write a message to parents about upcoming tests."],
                ),
                AgentSkill(
                    name="parent",
                    description="Parent voice and communication support.",
                    tags=["metagpt", "education", "parent"],
                    examples=["Draft a question to ask a student about their grades."],
                ),
                AgentSkill(
                    name="student",
                    description="Student persona: questions, reflections, and planning.",
                    tags=["metagpt", "education", "student"],
                    examples=["Respond to a parent about how you feel about your grades."],
                ),
                AgentSkill(
                    name="superintendent",
                    description="District-level communications and strategy reflections.",
                    tags=["metagpt", "education", "superintendent"],
                    examples=["Draft a district-wide statement about a new initiative."],
                ),
                AgentSkill(
                    name="school_board",
                    description="Board meeting prep, resolutions, and community messages.",
                    tags=["metagpt", "education", "school_board"],
                    examples=["Draft a short board resolution about a new program."],
                ),
                AgentSkill(
                    name="accountability_partner",
                    description="Helps set goals and follow-through steps as an accountability partner.",
                    tags=["metagpt", "coaching", "accountability"],
                    examples=["Help me plan and stay on track with weekly goals."],
                ),
            ],
        )

        super().__init__(agent_card=card)

    # ------------------------- MetaGPT call ------------------------- #

    def _call_metagpt(self, text: str, role: str) -> Any:
        """
        Call the MetaGPT FastAPI sidecar's /run endpoint.

        IMPORTANT: we do NOT silently rewrite unknown roles to 'analyst'.
        Whatever role we resolved gets passed straight through.
        """
        if role not in SUPPORTED_ROLES:
            logger.warning(
                "[MetaGPTA2AAgent] Role '%s' not in SUPPORTED_ROLES; passing through anyway",
                role,
            )

        payload = {"query": text, "role": role}

        logger.info(
            "[MetaGPTA2AAgent] Sending to MetaGPT/Ollama: role=%s payload_preview=%r",
            role,
            text[:300],
        )

        try:
            resp = httpx.post(
                f"{METAGPT_BASE_URL}/run",
                json=payload,
                timeout=600.0,
            )

            raw_body = resp.text

            logger.info(
                "[MetaGPTA2AAgent] Raw response from MetaGPT sidecar [%s]: %s",
                resp.status_code,
                raw_body[:2000],
            )

            resp.raise_for_status()
        except Exception as e:
            logger.exception("Error calling MetaGPT sidecar")
            return {"error": f"Error calling MetaGPT: {e}"}

        data = resp.json()
        result = data.get("result", data)

        logger.info(
            "[MetaGPTA2AAgent] Extracted result for role=%s: %r",
            role,
            result,
        )

        self._log_metagpt_call(
            role=role,
            text=text,
            raw_response_text=raw_body,
            result=result,
        )

        return result

    # ------------------------- Logging ------------------------- #

    def _log_metagpt_call(
        self,
        role: str,
        text: str,
        raw_response_text: str,
        result: Any,
    ) -> None:
        base_dir = Path(A2A_AGENT_LOG_DIR)
        base_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_role = role.replace("/", "_")
        log_path = base_dir / f"{ts}-{safe_role}.log"

        try:
            with log_path.open("w", encoding="utf-8") as f:
                f.write(f"--- MetaGPTA2AAgent Call ---\n")
                f.write(f"timestamp: {ts}\n")
                f.write(f"role: {role}\n\n")

                f.write("INPUT (query text sent to MetaGPT):\n")
                f.write(text)
                f.write("\n\n")

                f.write("RAW HTTP RESPONSE FROM METAGPT SIDECAR:\n")
                f.write(raw_response_text)
                f.write("\n\n")

                f.write("PARSED RESULT OBJECT:\n")
                try:
                    f.write(json.dumps(result, indent=2, ensure_ascii=False))
                except TypeError:
                    f.write(repr(result))
                f.write("\n")
        except Exception:
            logger.exception(
                "[MetaGPTA2AAgent] Failed to write per-call log at %s",
                log_path,
            )

    # ------------------------- Role/Text parsing ------------------------- #

    def _extract_role_and_text_from_task(self, task) -> Tuple[str, str]:
        """
        Parse the [role:...] header from the raw text and return (role, text_without_header).

        This is the single source of truth for the MetaGPT role:
        - We ignore task.skill and metadata for now.
        - If there's a [role:XYZ] header on the first line, use XYZ.
        - Otherwise, default to 'analyst'.
        """
        msg: Dict[str, Any] = task.message or {}
        content = msg.get("content", {})

        raw_text = ""
        if isinstance(content, dict):
            raw_text = content.get("text", "") or ""
        elif isinstance(content, str):
            raw_text = content
        else:
            raw_text = ""

        if not raw_text:
            logger.info("No text in task %s; defaulting to role=analyst", getattr(task, "id", ""))
            return "analyst", "No user text provided."

        lines = raw_text.splitlines()
        if not lines:
            return "analyst", raw_text

        first = lines[0].strip()
        m = ROLE_HEADER_RE.match(first)
        if m:
            role = m.group("role").strip() or "analyst"
            rest = "\n".join(lines[1:]).lstrip("\n")
            logger.info(
                "[MetaGPTA2AAgent] Resolved role from header: %r for task %s",
                role,
                getattr(task, "id", ""),
            )
            return role, rest or "No user text provided."
        else:
            logger.info(
                "[MetaGPTA2AAgent] No [role:...] header found for task %s; defaulting to 'analyst'",
                getattr(task, "id", ""),
            )
            return "analyst", raw_text

    # -------------------------- A2A hook --------------------------- #

    def handle_task(self, task):
        """
        Main entry point called by python-a2a for each incoming Task.
        """
        # 1) Resolve role + text from the task (using [role:...] header)
        role, text = self._extract_role_and_text_from_task(task)

        # 2) Call MetaGPT with that role + text
        result = self._call_metagpt(text, role=role)

        # 3) Wrap in A2A artifact
        task.artifacts = [
            {
                "parts": [
                    {
                        "type": "text",
                        "text": str(result),
                    }
                ]
            }
        ]

        # 4) Mark completed
        task.status = TaskStatus(state=TaskState.COMPLETED)
        logger.info("Task %s completed (role=%s)", getattr(task, "id", ""), role)
        return task


# --------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------

def main() -> None:
    agent = MetaGPTA2AAgent()
    run_server(agent, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
