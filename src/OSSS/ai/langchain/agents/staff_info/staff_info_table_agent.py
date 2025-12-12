from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol, get_llm
from langchain_core.messages import HumanMessage

from OSSS.ai.langchain.tools.staff_info.staff_info_table_tool import build_staff_info_table_tool

logger = logging.getLogger("OSSS.ai.langchain.staff_info_table_agent")


class StaffInfoTableAgent(LangChainAgentProtocol):
    name = "lc.staff_info_table"

    def __init__(self) -> None:
        self.llm = get_llm()
        self.tool = build_staff_info_table_tool()

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Simple behavior: call tool with no filters.
        Later you can add a small parser that extracts filters from message.
        """
        sid = session_id or ""
        logger.info("[staff_info_agent] run session_id=%s message=%r", sid, message[:200])

        # Start simple: always run tool without filters
        reply = await self.tool.ainvoke({"filters": None, "session_id": sid, "skip": 0, "limit": 100})
        return {"reply": reply, "agent": self.name}
