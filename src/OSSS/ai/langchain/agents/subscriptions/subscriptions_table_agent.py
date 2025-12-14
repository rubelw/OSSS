# Auto-generated LangChain agent for QueryData mode="subscriptions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .subscriptions_table import SubscriptionsFilters, run_subscriptions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.subscriptions")

class SubscriptionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `subscriptions`.
    """

    name = "lc.subscriptions_table"
    intent = "subscriptions"
    intent_aliases = ['subscriptions', 'list subscriptions', 'subscription list', 'show subscriptions', 'all subscriptions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_subscriptions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SubscriptionsTableAgent())
