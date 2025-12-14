from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import re

from OSSS.ai.langchain.base import LangChainAgentProtocol
from .buildings_table import BuildingsFilters, run_buildings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.buildings")

DEFAULT_SKIP = 0
DEFAULT_LIMIT = 100


def _parse_skip_limit(message: str) -> tuple[int, int]:
    skip = DEFAULT_SKIP
    limit = DEFAULT_LIMIT
    if not isinstance(message, str):
        return skip, limit

    m_skip = re.search(r"\bskip\b\s*(?:=)?\s*(\d+)\b", message, flags=re.I)
    m_limit = re.search(r"\blimit\b\s*(?:=)?\s*(\d+)\b", message, flags=re.I)

    if m_skip:
        try:
            skip = max(0, int(m_skip.group(1)))
        except Exception:
            pass
    if m_limit:
        try:
            limit = max(1, min(5000, int(m_limit.group(1))))
        except Exception:
            pass

    return skip, limit


class BuildingsTableAgent(LangChainAgentProtocol):
    name = "lc.buildings_table"
    intent = "buildings"
    intent_aliases = [
        "building",
        "buildings",
        "school buildings",
        "district buildings",
        "facilities",
        "facility list",
        "show buildings",
        "list buildings",
    ]

    async def run(self, message: str, session_id: Optional[str] = None, **_: Any) -> Dict[str, Any]:
        skip, limit = _parse_skip_limit(message or "")

        # (optional) later: parse filters from message; for now, no filters
        filters = BuildingsFilters()

        result = await run_buildings_table_structured(
            filters=filters,
            session_id=session_id or "unknown",
            skip=skip,
            limit=limit,
        )

        # Keep registry-friendly shape
        return {
            "reply": result["reply"],
            "rows": result.get("rows"),
            "filters": result.get("filters"),
            "agent": self.name,
            "intent": self.intent,
            "meta": {
                "skip": skip,
                "limit": limit,
            },
        }
