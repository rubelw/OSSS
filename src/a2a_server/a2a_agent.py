"""
MetaGPT-backed A2A Agent

This module defines a python-a2a Agent that *wraps* your MetaGPT FastAPI
sidecar and exposes it over the A2A protocol.

Overall flow:

  A2A Client (orchestrator)  -->  this Agent (python-a2a)  -->  MetaGPT HTTP sidecar

1. The orchestrator sends a Task (with text + optional [role:...] header).
2. python-a2a calls `MetaGPTA2AAgent.handle_task(task)`.
3. We decide which MetaGPT role to use (analyst, data_interpreter, etc.).
4. We call MetaGPT's /run endpoint with {query, role}.
5. We wrap MetaGPT's result in A2A artifacts and mark the task COMPLETED.
"""

import os
import logging
from typing import Any, Dict

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
# In docker-compose, the MetaGPT service is typically named "metagpt"
# and exposes its FastAPI on port 8001.
#
# Example docker-compose snippet:
#   metagpt:
#       container_name: metagpt
#       ports:
#         - "8001:8001"
#
# We default to that internal service name, but allow overrides via env.
METAGPT_BASE_URL = os.getenv("METAGPT_BASE_URL", "http://metagpt:8001")

# Supported MetaGPT roles that this A2A agent knows how to route to.
# These must match the role names in your MetaGPT roles_registry (team setup).
SUPPORTED_ROLES = [
    "analyst",
    "principal",
    "principal_email",
    "principal_discipline",
    "principal_announcement",
]

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# --------------------------------------------------------------------
# Agent implementation
# --------------------------------------------------------------------

class MetaGPTA2AAgent(A2AServer):
    """
    A python-a2a Agent that proxies tasks to a MetaGPT sidecar.

    Responsibilities:
      - Advertise itself and its capabilities (AgentCard + AgentSkill list)
      - Accept A2A Tasks via HTTP (handled by python-a2a)
      - Decide which MetaGPT role to use per task
      - Call MetaGPT's `/run` endpoint with (query, role)
      - Return results back to the A2A client as text artifacts
    """

    def __init__(self) -> None:
        """
        Initialize the agent and register its "card" with python-a2a.

        The AgentCard is like a business card for this agent:
          - name / description / version / url
          - list of skills (e.g., analyst, data_interpreter)

        Other services (like your orchestrator or a registry) can discover
        what this agent does by reading this metadata.
        """
        card = AgentCard(
            name="MetaGPT Multi-Role Agent",
            description=(
                "Wraps multiple MetaGPT roles (analyst, data_interpreter) "
                "and exposes them over the A2A protocol."
            ),
            # URL where this agent is reachable inside docker-compose.
            # This is informational metadata for discovery/docs; python-a2a
            # already knows the local bind address when run_server(...) is used.
            url="http://a2a-agent:9000",  # or "" if you don't want a public URL
            version="0.1.0",
            skills=[
                AgentSkill(
                    name="analyst",
                    description="Use MetaGPT's MyAnalystRole for structured analysis.",
                    tags=["metagpt", "analysis"],
                    examples=["Analyze the local economic impact of AI adoption."],
                ),
                # ---- principal variants ----
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
            ],
        )

        # Initialize the base A2AServer with this card so that:
        # - python-a2a can serve metadata about this agent
        # - incoming tasks are routed to handle_task(...)
        super().__init__(agent_card=card)

    # ------------------------- MetaGPT call ------------------------- #

    def _call_metagpt(self, text: str, role: str) -> Any:
        """
        Call the MetaGPT FastAPI sidecar's /run endpoint.

        Expectation: your MetaGPT FastAPI exposes something like:

            POST /run
            {
                "query": "...",     # user text / prompt
                "role": "analyst"   # role name, e.g., "analyst" or "data_interpreter"
            }

        And it returns a JSON payload, e.g.:

            {
                "role": "analyst",
                "result": "<anything JSON-serializable>"
            }

        We return the "result" portion if present, or the full response body.
        """
        # Sanity check the requested role; default to analyst if unknown.
        if role not in SUPPORTED_ROLES:
            logger.warning("Unknown role '%s', defaulting to 'analyst'", role)
            role = "analyst"

        payload = {"query": text, "role": role}
        logger.info("Calling MetaGPT at %s/run with role=%s", METAGPT_BASE_URL, role)

        try:
            resp = httpx.post(
                f"{METAGPT_BASE_URL}/run",
                json=payload,
                timeout=600.0,  # generous timeout for large MetaGPT chains
            )
            resp.raise_for_status()
        except Exception as e:
            # Log stack trace for server logs.
            logger.exception("Error calling MetaGPT sidecar")
            # Return an error payload as the "result" so the caller
            # gets something structured back, rather than exploding.
            return {"error": f"Error calling MetaGPT: {e}"}

        data = resp.json()
        # Common pattern: { "role": "...", "result": <payload> }
        return data.get("result", data)

    # ------------------------- Task parsing ------------------------- #

    def _extract_role_from_task(self, task) -> str:
        """
        Decide which MetaGPT role to use for a given task.

        We support several ways to specify role, in this order of precedence:

        1) task.skill (set by the A2A client / orchestrator)
           - This is the canonical place for the "skill" name in python-a2a.

        2) task.message.metadata.role
           - For clients that stuff the role into message metadata.

        3) [role:...] header at the top of message.content.text
           - For clients that only send text but encode control hints in-band:
             e.g., "[role:data_interpreter]\\nPlease inspect this CSV..."

        4) If nothing matches, default to 'analyst'.
        """
        role = None

        # 1) If python-a2a Task exposes a `skill` attribute and it matches our roles.
        if getattr(task, "skill", None) in SUPPORTED_ROLES:
            role = task.skill

        # 2) If there's metadata on the message and it has a valid role.
        msg: Dict[str, Any] = task.message or {}
        metadata = msg.get("metadata", {})
        if not role and isinstance(metadata, dict):
            candidate = metadata.get("role")
            if candidate in SUPPORTED_ROLES:
                role = candidate

        # 3) Fallback: parse [role:...] header from the first line of text
        if not role:
            content = msg.get("content", {})
            text_candidate = ""
            if isinstance(content, dict):
                text_candidate = content.get("text", "") or ""

            # Look for a first-line header like: [role:data_interpreter]
            if isinstance(text_candidate, str) and text_candidate.startswith("[role:"):
                first_line, _, _ = text_candidate.partition("\n")
                inner = ""
                if first_line.endswith("]"):
                    # Strip leading "[role:" and trailing "]"
                    inner = first_line[len("[role:"):-1]
                else:
                    # Fallback if the closing ']' is missing
                    inner = first_line[len("[role:"):]
                inner = inner.strip()

                if inner in SUPPORTED_ROLES:
                    role = inner

        # 4) Default role if nothing else matched
        if not role:
            role = "analyst"

        logger.info(
            "Using MetaGPT role '%s' for task %s",
            role,
            getattr(task, "id", ""),
        )
        return role

    def _extract_text_from_task(self, task) -> str:
        """
        Extract the user-visible text from the A2A task's message.

        A typical python-a2a Task.message structure looks like:

            task.message = {
                "role": "user",
                "content": {
                    "text": "...",
                    ...
                },
                "metadata": {...}
            }

        We:
          - Safely extract `content["text"]`
          - Provide a fallback message if empty
          - Strip an optional leading [role:...] header that the orchestrator
            may have added, so that MetaGPT doesn't see control headers.
        """
        msg: Dict[str, Any] = task.message or {}
        content = msg.get("content", {})

        text = ""
        if isinstance(content, dict):
            text = content.get("text", "") or ""

        if not text:
            # If no text was provided at all, pass a placeholder.
            text = "No user text provided."
        else:
            # Strip [role:...] header if present in the first line.
            if text.startswith("[role:"):
                first_line, sep, rest = text.partition("\n")
                # Only strip if there is at least one newline following the header.
                if sep:  # sep == '\n' if a newline was found
                    text = rest or ""

        logger.info(
            "Extracted text for task %s: %.80r",
            getattr(task, "id", ""),
            text,
        )
        return text

    # -------------------------- A2A hook --------------------------- #

    def handle_task(self, task):
        """
        The main entry point called by python-a2a for each incoming Task.

        High-level sequence:
          1) Determine which MetaGPT role to use for this task.
          2) Extract the user text from the task.
          3) Call MetaGPT's /run endpoint.
          4) Wrap the result in an A2A artifact.
          5) Mark the task COMPLETED and return it.

        python-a2a handles the HTTP plumbing and JSON decoding/encoding;
        you only implement this method to wire business logic.
        """
        # 1) Resolve the MetaGPT role.
        role = self._extract_role_from_task(task)

        # 2) Extract the text to be sent as MetaGPT "query".
        text = self._extract_text_from_task(task)

        # 3) Call the MetaGPT sidecar with that text + role.
        result = self._call_metagpt(text, role=role)

        # 4) A2A artifact schema: we create a single artifact with one text part.
        #    More complex agents might add multiple artifacts, files, images, etc.
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

        # 5) Mark the task as COMPLETED in the A2A protocol.
        task.status = TaskStatus(state=TaskState.COMPLETED)
        logger.info("Task %s completed", getattr(task, "id", ""))
        return task


# --------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------

def main() -> None:
    """
    Standard Python entrypoint to run this agent as a standalone HTTP server.

    By default, we:
      - Bind to 0.0.0.0 (inside a container)
      - Listen on port 9000
      - Let python-a2a's `run_server` handle HTTP + routing details
    """
    agent = MetaGPTA2AAgent()
    run_server(agent, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    # If this module is executed as a script (`python a2a_agent.py`),
    # start the agent server. In docker-compose, you typically run:
    #
    #   command: python -m a2a_server.a2a_agent
    #
    # which will also land here.
    main()
