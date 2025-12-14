# Auto-generated LangChain agent for QueryData mode="sis_import_jobs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .sis_import_jobs_table import SisImportJobsFilters, run_sis_import_jobs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.sis_import_jobs")

class SisImportJobsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `sis_import_jobs`.
    """

    name = "lc.sis_import_jobs_table"
    intent = "sis_import_jobs"
    intent_aliases = ['sis_import_jobs', 'sis import jobs', 'SIS import history', 'SIS sync jobs', 'import job status', 'SIS data imports', 'student information system imports', 'show sis import jobs', 'list sis import jobs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_sis_import_jobs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SisImportJobsTableAgent())
