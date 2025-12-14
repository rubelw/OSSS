# Auto-generated LangChain agent for QueryData mode="meal_accounts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meal_accounts_table import MealAccountsFilters, run_meal_accounts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meal_accounts")

class MealAccountsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meal_accounts`.
    """

    name = "lc.meal_accounts_table"
    intent = "meal_accounts"
    intent_aliases = ['meal accounts', 'meal_accounts', 'lunch accounts', 'cafeteria accounts', 'dcg meal accounts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meal_accounts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MealAccountsTableAgent())
