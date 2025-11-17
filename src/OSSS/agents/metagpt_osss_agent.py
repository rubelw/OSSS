# src/OSSS/agents/metagpt_osss_agent.py
from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger

from metagpt.roles import ProductManager, Architect, ProjectManager, Engineer
from metagpt.team import Team


async def run_osss_metagpt_agent(
    requirement: str,
    investment: float = 2.0,
    workspace: Optional[str] = None,
) -> None:
    """
    Run a MetaGPT team for the given requirement.

    NOTE: MetaGPT 0.8.x Team does NOT expose `set_workspace`, so we let it
    manage its own workspace (usually under ./workspace) based on config2.yaml.
    """
    logger.info(f"Starting OSSS MetaGPT agent: requirement={requirement!r}, investment={investment}, workspace={workspace!r}")

    # Create a "company" team
    team = Team()

    # Hire roles similar to the official startup example
    team.hire(
        [
            ProductManager(),
            Architect(),
            ProjectManager(),
            Engineer(),  # you can tweak n_borg/use_code_review here if you like
        ]
    )

    # Set budget
    team.invest(investment=investment)

    # Register the project/idea
    team.run_project(idea=requirement)

    # Optionally you *could* log the workspace argument just for your own tracking
    if workspace:
        logger.info(f"(MetaGPT) workspace hint={workspace!r} (note: Team.set_workspace is not available in 0.8.x)")

    # Run a few rounds – adjust as you see fit
    await team.run(n_round=5)

    logger.info(f"OSSS MetaGPT agent finished for requirement={requirement!r}")
