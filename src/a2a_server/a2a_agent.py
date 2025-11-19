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

# Where the MetaGPT FastAPI sidecar is reachable *from this container*
# In docker-compose, this will typically be http://metagpt:8001
METAGPT_BASE_URL = os.getenv("METAGPT_BASE_URL", "http://metagpt:8001")

# These must match the role names in your MetaGPT roles_registry
SUPPORTED_ROLES = ["analyst", "data_interpreter"]

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# --------------------------------------------------------------------
# Agent implementation
# --------------------------------------------------------------------

class MetaGPTA2AAgent(A2AServer):
    """
    A python-a2a Agent that proxies tasks to a MetaGPT sidecar.

    - Exposes an A2A-compliant HTTP interface.
    - For each task, picks a MetaGPT role and calls POST /run on the sidecar.
    """

    def __init__(self) -> None:
        # AgentCard describes this agent and its skills to the A2A world
        card = AgentCard(
            name="MetaGPT Multi-Role Agent",
            description=(
                "Wraps multiple MetaGPT roles (analyst, data_interpreter) "
                "and exposes them over the A2A protocol."
            ),
            url="http://a2a-agent:9000",  # or "" if you don't want to expose a public URL
            version="0.1.0",
            skills=[
                AgentSkill(
                    name="analyst",
                    description="Use MetaGPT's MyAnalystRole for structured analysis.",
                    tags=["metagpt", "analysis"],
                    examples=["Analyze the local economic impact of AI adoption."],
                ),
                AgentSkill(
                    name="data_interpreter",
                    description="Use MetaGPT's DataInterpreter to inspect or explain data/text.",
                    tags=["metagpt", "data"],
                    examples=["Summarize a CSV description or query logs."],
                ),
            ],
        )

        super().__init__(agent_card=card)

    # ------------------------- MetaGPT call ------------------------- #

    def _call_metagpt(self, text: str, role: str) -> Any:
        """
        Call the MetaGPT FastAPI sidecar's /run endpoint.

        Expects MetaGPT metagpt_server.py to expose:

            POST /run
            { "query": "...", "role": "analyst" }

        And return:
            { "role": "...", "result": <anything JSON-serializable> }
        """
        if role not in SUPPORTED_ROLES:
            logger.warning("Unknown role '%s', defaulting to 'analyst'", role)
            role = "analyst"

        payload = {"query": text, "role": role}
        logger.info("Calling MetaGPT at %s/run with role=%s", METAGPT_BASE_URL, role)

        try:
            resp = httpx.post(
                f"{METAGPT_BASE_URL}/run",
                json=payload,
                timeout=600.0,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.exception("Error calling MetaGPT sidecar")
            # Return an error payload as the "result"
            return {"error": f"Error calling MetaGPT: {e}"}

        data = resp.json()
        # Your metagpt_server likely returns {"role": "...", "result": ...}
        return data.get("result", data)

    # ------------------------- Task parsing ------------------------- #

    def _extract_role_from_task(self, task) -> str:
        """
        Decide which MetaGPT role to use for a given task.

        Priority:
        1) task.skill (from python-a2a)
        2) task.message.metadata.role
        3) [role:...] header at top of content.text
        4) fallback to 'analyst'
        """
        role = None

        # 1) If python-a2a Task exposes a `skill` property and it matches our roles
        if getattr(task, "skill", None) in SUPPORTED_ROLES:
            role = task.skill

        # 2) If there's metadata on the message
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

            if isinstance(text_candidate, str) and text_candidate.startswith("[role:"):
                first_line, _, _ = text_candidate.partition("\n")
                inner = ""
                if first_line.endswith("]"):
                    inner = first_line[len("[role:"):-1]
                else:
                    inner = first_line[len("[role:"):]
                inner = inner.strip()

                if inner in SUPPORTED_ROLES:
                    role = inner

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

        By convention, A2A message schema often looks like:

        task.message = {
            "role": "user",
            "content": {
                "text": "...",
                ...
            },
            "metadata": {...}
        }

        We also strip an optional leading [role:...] header that the orchestrator
        may have added to steer role selection.
        """
        msg: Dict[str, Any] = task.message or {}
        content = msg.get("content", {})

        text = ""
        if isinstance(content, dict):
            text = content.get("text", "") or ""

        if not text:
            text = "No user text provided."
        else:
            # Strip [role:...] header if present
            if text.startswith("[role:"):
                first_line, sep, rest = text.partition("\n")
                # Only strip if the first line looks like a header
                if sep:  # there was a newline
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
        Core A2A glue:

        1) Choose MetaGPT role from the task.
        2) Extract user text from the task.
        3) Call MetaGPT sidecar.
        4) Attach artifacts and mark the task COMPLETED.

        This is the method python-a2a calls for each incoming task.
        """
        role = self._extract_role_from_task(task)
        text = self._extract_text_from_task(task)
        result = self._call_metagpt(text, role=role)

        # A2A artifact schema: simplest form is a single text part
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

        task.status = TaskStatus(state=TaskState.COMPLETED)
        logger.info("Task %s completed", getattr(task, "id", ""))
        return task


# --------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------

def main() -> None:
    agent = MetaGPTA2AAgent()
    # Expose HTTP A2A endpoint on port 9000
    run_server(agent, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
