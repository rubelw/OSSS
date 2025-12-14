# Auto-generated LangChain agent for QueryData mode="live_scorings"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .live_scorings_table import LiveScoringsFilters, run_live_scorings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.live_scorings")

class LiveScoringsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `live_scorings`.
    """

    name = "lc.live_scorings_table"
    intent = "live_scorings"
    intent_aliases = ['live scoring', 'live score', 'live scores', 'live game', 'game score', 'sports live scoring']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_live_scorings_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(LiveScoringsTableAgent())
