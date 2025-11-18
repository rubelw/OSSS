from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal

from loguru import logger

from metagpt.roles import ProductManager, Architect, ProjectManager, Engineer
from metagpt.team import Team
from metagpt.llm import LLM

import json
from datetime import datetime
from pathlib import Path

LOG_ROOT = Path("/workspace/logs")
LOG_ROOT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# 1) Main OSSS MetaGPT Team-based agent
# ---------------------------------------------------------


async def run_osss_metagpt_agent(
    requirement: str,
    investment: float = 2.0,
    workspace: Optional[str] = None,
) -> None:
    """
    Main OSSS MetaGPT agent.

    Spins up a MetaGPT Team (PM, Architect, PMgr, Engineer), invests a budget,
    and runs the project on the given `requirement`.
    """
    logger.info(
        "Starting OSSS MetaGPT agent: requirement=%r, investment=%s, workspace=%r",
        requirement,
        investment,
        workspace,
    )

    team = Team()
    team.hire(
        [
            ProductManager(),
            Architect(),
            ProjectManager(),
            Engineer(),
        ]
    )

    # Set the "budget" (how many steps / tokens it can burn)
    team.invest(investment=investment)
    logger.info("Team investment set to $%s.", investment)

    # Kick off the project with the requirement text
    # (this is the pattern that produced your crm_simple example)
    team.run_project(idea=requirement)

    if workspace:
        # MetaGPT 0.8.x Team has no set_workspace; just log the hint.
        logger.info(
            "(MetaGPT) workspace hint=%r (note: Team.set_workspace is not available in 0.8.x)",
            workspace,
        )

    # Run a few rounds; tune n_round if you want more/less depth
    await team.run(n_round=5)

    logger.info("OSSS MetaGPT agent finished for requirement=%r", requirement)


# ---------------------------------------------------------
# 2) Simple 2-agent conversational demo
# ---------------------------------------------------------


@dataclass
class SimpleAgent:
    """A lightweight conversational agent built on MetaGPT's LLM."""
    name: str
    role: str
    goal: str

    async def reply(self, llm: LLM, conversation: list[dict[str, str]]) -> str:
        """
        Given the conversation so far, produce the next message
        from this agent's point of view.
        """
        system_prompt = f"""
You are {self.name}, acting as: {self.role}.

Goal: {self.goal}

You are collaborating with another agent. Read the conversation so far
and respond with a short, concrete contribution that moves things forward.
Avoid repeating yourself. Be specific and practical.
"""

        # keep only last few messages to avoid very long prompts
        short_history = conversation[-10:]

        history_text = "\n".join(f"{m['speaker']}: {m['text']}" for m in short_history)
        prompt = (
            f"{system_prompt}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            f"Your next turn ({self.name}):"
        )

        response = await llm.aask(prompt)
        return response.strip()


async def run_two_osss_agents_conversation(
    topic: str,
    rounds: int = 4,
) -> list[dict[str, str]]:
    """
    Example: two agents (Principal & OSSS Architect) discuss an OSSS topic.

    Returns the conversation as a list of {'speaker', 'text'} dicts.
    """
    llm = LLM()  # uses /root/.metagpt/config2.yaml (Ollama mistral:latest)

    principal = SimpleAgent(
        name="Principal",
        role="School building principal at a mid-sized public district",
        goal=f"Explain real-world needs, constraints, and use cases around: {topic}",
    )

    architect = SimpleAgent(
        name="Architect",
        role="OSSS systems architect",
        goal=(
            "Propose concrete OSSS-based technical approaches, integrating FastAPI, "
            "Postgres, Keycloak, Redis, Trino, Superset, Rasa, and existing OSSS services."
        ),
    )

    conversation: list[dict[str, str]] = []
    conversation.append(
        {
            "speaker": "System",
            "text": (
                f"Topic: {topic}. The Principal explains needs; the Architect proposes "
                "realistic OSSS implementations in response."
            ),
        }
    )

    speaker_order: list[Literal["Principal", "Architect"]] = ["Principal", "Architect"]

    for i in range(rounds):
        for who in speaker_order:
            agent = principal if who == "Principal" else architect
            logger.info(
                "Two-agent chat: %s is speaking (round %s)...", agent.name, i + 1
            )
            reply_text = await agent.reply(llm=llm, conversation=conversation)
            conversation.append({"speaker": agent.name, "text": reply_text})

    # ---- LOG TO /workspace/logs ----
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    log_file = LOG_ROOT / f"conversation_{timestamp}.json"
    log_file.write_text(json.dumps(conversation, indent=2))

    logger.info("Two-agent OSSS conversation finished.")
    return conversation
