# Auto-generated LangChain agent for QueryData mode="data_sharing_agreements"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .data_sharing_agreements_table import DataSharingAgreementsFilters, run_data_sharing_agreements_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.data_sharing_agreements")

class DataSharingAgreementsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `data_sharing_agreements`.
    """

    name = "lc.data_sharing_agreements_table"
    intent = "data_sharing_agreements"
    intent_aliases = ['data sharing agreements', 'data_sharing_agreements', 'vendor data agreements', 'student data sharing agreements', 'dpa agreements']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_data_sharing_agreements_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DataSharingAgreementsTableAgent())
