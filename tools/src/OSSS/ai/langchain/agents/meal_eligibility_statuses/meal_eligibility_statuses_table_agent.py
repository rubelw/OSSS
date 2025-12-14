# Auto-generated LangChain agent for QueryData mode="meal_eligibility_statuses"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meal_eligibility_statuses_table import MealEligibilityStatusesFilters, run_meal_eligibility_statuses_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meal_eligibility_statuses")

class MealEligibilityStatusesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meal_eligibility_statuses`.
    """

    name = "lc.meal_eligibility_statuses_table"
    intent = "meal_eligibility_statuses"
    intent_aliases = ['meal eligibility statuses', 'meal_eligibility_statuses', 'meal eligibility', 'lunch eligibility', 'free reduced lunch status', 'dcg meal eligibility']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meal_eligibility_statuses_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MealEligibilityStatusesTableAgent())
