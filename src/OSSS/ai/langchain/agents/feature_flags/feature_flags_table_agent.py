# Auto-generated LangChain agent for QueryData mode="feature_flags"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .feature_flags_table import FeatureFlagsFilters, run_feature_flags_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.feature_flags")

class FeatureFlagsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `feature_flags`.
    """

    name = "lc.feature_flags_table"
    intent = "feature_flags"
    intent_aliases = ['feature flags', 'feature_flags', 'toggle flags', 'feature toggles', 'app flags', 'flag list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_feature_flags_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FeatureFlagsTableAgent())
