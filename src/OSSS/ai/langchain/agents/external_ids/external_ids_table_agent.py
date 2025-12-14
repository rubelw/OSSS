# Auto-generated LangChain agent for QueryData mode="external_ids"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .external_ids_table import ExternalIdsFilters, run_external_ids_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.external_ids")

class ExternalIdsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `external_ids`.
    """

    name = "lc.external_ids_table"
    intent = "external_ids"
    intent_aliases = ['external_ids', 'external ids', 'external id mapping', 'sis ids', 'state ids', 'vendor ids', 'mapping to external systems']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_external_ids_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ExternalIdsTableAgent())
