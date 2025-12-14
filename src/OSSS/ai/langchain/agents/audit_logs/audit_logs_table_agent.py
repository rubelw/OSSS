# Auto-generated LangChain agent for QueryData mode="audit_logs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .audit_logs_table import AuditLogsFilters, run_audit_logs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.audit_logs")

class AuditLogsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `audit_logs`.
    """

    name = "lc.audit_logs_table"
    intent = "audit_logs"
    intent_aliases = ['audit logs', 'audit_logs', 'activity logs', 'change history']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_audit_logs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AuditLogsTableAgent())
