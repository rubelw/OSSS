# Auto-generated LangChain agent for QueryData mode="policy_files"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_files_table import PolicyFilesFilters, run_policy_files_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_files")

class PolicyFilesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_files`.
    """

    name = "lc.policy_files_table"
    intent = "policy_files"
    intent_aliases = ['policy files', 'policy_files', 'files for policies', 'policy file attachments', 'dcg policy files', 'osss policy files']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_files_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyFilesTableAgent())
