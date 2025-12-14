# Auto-generated LangChain agent for QueryData mode="materials"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .materials_table import MaterialsFilters, run_materials_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.materials")

class MaterialsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `materials`.
    """

    name = "lc.materials_table"
    intent = "materials"
    intent_aliases = ['materials', 'materials list', 'material list', 'supply list', 'supplies list', 'classroom materials', 'teaching materials']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_materials_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MaterialsTableAgent())
