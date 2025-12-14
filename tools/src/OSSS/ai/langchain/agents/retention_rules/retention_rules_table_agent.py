# Auto-generated LangChain agent for QueryData mode="retention_rules"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .retention_rules_table import RetentionRulesFilters, run_retention_rules_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.retention_rules")

class RetentionRulesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `retention_rules`.
    """

    name = "lc.retention_rules_table"
    intent = "retention_rules"
    intent_aliases = ['retention rules', 'retention_rules', 'data retention rules', 'record retention', 'policy retention rules', 'how long do we retain', 'retention schedule', 'retention policy']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_retention_rules_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(RetentionRulesTableAgent())
