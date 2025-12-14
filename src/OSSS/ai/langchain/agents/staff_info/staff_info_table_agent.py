# src/OSSS/ai/langchain/agents/staff_info/staff_info_table_agent.py
from __future__ import annotations

import json
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol, get_llm
from OSSS.ai.langchain.tools.staff_info.staff_info_table_tool import build_staff_info_table_tool
from OSSS.ai.agents.base import AgentResult

logger = logging.getLogger("OSSS.ai.langchain.staff_info_table_agent")


class StaffInfoTableAgent(LangChainAgentProtocol):
    name = "lc.staff_info_table"

    def __init__(self) -> None:
        self.llm = get_llm()
        self.tool = build_staff_info_table_tool()

    async def run(self, message: str, session_id: str | None = None, **_kwargs):
        user_text = message or ""
        logger.info("[staff_info_agent] run session_id=%s message=%r", session_id, user_text[:200])

        # Tool requires a non-null session_id string
        sid = session_id or "anonymous"  # or raise if you truly require it

        tool_result = await self.tool.ainvoke(
            {"filters": None, "session_id": sid, "skip": 0, "limit": 100}
        )

        if isinstance(tool_result, str):
            answer_text = tool_result
        else:
            answer_text = json.dumps(tool_result, indent=2, default=str)

        return AgentResult(
            answer_text=answer_text,
            intent="staff_directory",
            agent_id="staff_directory",
            agent_name=self.name,
            status="ok",
            extra_chunks=[],
            agent_session_id=sid,
            data={"tool_result": tool_result},
        )
