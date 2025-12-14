# Auto-generated LangChain agent for QueryData mode="report_cards"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .report_cards_table import ReportCardsFilters, run_report_cards_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.report_cards")

class ReportCardsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `report_cards`.
    """

    name = "lc.report_cards_table"
    intent = "report_cards"
    intent_aliases = ['report_cards', 'report cards', 'show report cards', 'list report cards', 'student report cards', 'grade report cards', 'dcg report cards', 'osss report cards']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_report_cards_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ReportCardsTableAgent())
