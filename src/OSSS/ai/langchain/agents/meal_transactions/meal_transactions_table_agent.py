# Auto-generated LangChain agent for QueryData mode="meal_transactions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meal_transactions_table import MealTransactionsFilters, run_meal_transactions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meal_transactions")

class MealTransactionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meal_transactions`.
    """

    name = "lc.meal_transactions_table"
    intent = "meal_transactions"
    intent_aliases = ['meal transactions', 'meal_transactions', 'lunch transactions', 'cafeteria transactions', 'dcg meal transactions', 'osss meal transactions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meal_transactions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MealTransactionsTableAgent())
