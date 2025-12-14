from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import re

from pydantic import BaseModel, Field

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.agents.goals.goals_table import (
    GoalsFilters,
    run_goals_table_structured,
)

logger = logging.getLogger("OSSS.ai.langchain.goals_table_agent")


class GoalsToolArgs(BaseModel):
    """
    Minimal, stable args surface. You can make this richer later.
    """
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
    filters: Optional[GoalsFilters] = None


def _parse_skip_limit(text: str) -> tuple[int, int]:
    """
    Very small heuristic parsing:
      - "skip=10 limit=50"
      - "limit 25"
    """
    if not isinstance(text, str):
        return 0, 100

    skip = 0
    limit = 100

    m1 = re.search(r"\bskip\s*=\s*(\d+)\b", text, flags=re.IGNORECASE)
    if m1:
        skip = int(m1.group(1))

    m2 = re.search(r"\blimit\s*=\s*(\d+)\b", text, flags=re.IGNORECASE)
    if m2:
        limit = int(m2.group(1))
    else:
        m3 = re.search(r"\blimit\s+(\d+)\b", text, flags=re.IGNORECASE)
        if m3:
            limit = int(m3.group(1))

    limit = max(1, min(limit, 500))
    skip = max(0, skip)
    return skip, limit


class GoalsTableAgent(LangChainAgentProtocol):
    """
    LangChain-style agent that returns a goals table / summary from QueryData(mode='goals').

    Contract expectations in your repo:
      - .name : str  (registry key)
      - .run(message, session_id=...) -> dict
      - (optional) .intent, .intent_aliases used by your alias collector
    """

    name = "lc.goals_table"

    # used by your dynamic alias collector (_get_agent_aliases)
    intent = "goals"
    intent_aliases = [
        "goals",
        "district goals",
        "student goals",
        "academic goals",
        "behavior goals",
        "iep goals",
        "school improvement goals",
        "show goals",
        "list goals",
    ]

    async def run(self, message: str, session_id: Optional[str] = None, **_: Any) -> Dict[str, Any]:
        skip, limit = _parse_skip_limit(message or "")

        # Keep filters simple for now; you can parse plan_id/status later if you want.
        args = GoalsToolArgs(skip=skip, limit=limit, filters=None)

        logger.info(
            "[goals_table_agent] run session_id=%s skip=%s limit=%s",
            session_id,
            args.skip,
            args.limit,
        )

        result = await run_goals_table_structured(
            filters=args.filters,
            session_id=session_id or "",
            skip=args.skip,
            limit=args.limit,
        )

        # keep the output shape consistent with your registry expectations
        return {
            "reply": result.get("reply", ""),
            "rows": result.get("rows", []),
            "filters": result.get("filters"),
            "agent": self.name,
            "intent": self.intent,
        }
