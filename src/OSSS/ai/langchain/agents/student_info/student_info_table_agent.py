from __future__ import annotations

import logging
from typing import Any, Optional

from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from OSSS.ai.agents.base import AgentResult
from OSSS.ai.langchain.base import LangChainAgentProtocol, get_llm
from OSSS.ai.langchain.tools.student_info.student_info_table_tool import (
    student_info_table_tool,
)

logger = logging.getLogger("OSSS.ai.langchain.student_info_table_agent")


class StudentInfoTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that uses the `student_info_table` StructuredTool.
    """

    name = "lc.student_info_table"

    def __init__(self) -> None:
        llm = get_llm()
        tools = [student_info_table_tool]

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an assistant that summarizes and lists student information "
                        "from the OSSS backend.\n\n"
                        "Use the `student_info_table` tool whenever the user asks about "
                        "students (e.g., 'show male students', 'students in THIRD grade', "
                        "'last name beginning with S', etc.).\n\n"
                        "Map natural-language filters into the tool arguments:\n"
                        "- Use last_name_prefix for 'last name beginning with ...'.\n"
                        "- Use first_name_prefix for 'first name starting with ...'.\n"
                        "- Use genders=['FEMALE'] or ['MALE'] for gender queries.\n"
                        "- Use grade_levels=['THIRD'] etc. for grade-level filters.\n"
                        "- Use enrolled_only=False for 'withdrawn', 'inactive', 'not enrolled'.\n"
                        "- Use enrolled_only=True for 'currently enrolled', 'active', 'enrolled only'.\n\n"
                        "Always call `student_info_table` at least once per user request. "
                        "In your final answer, primarily return the markdown table the tool "
                        "produces, along with any minimal explanation if helpful. "
                        "Do NOT create your own synthetic table; use the tool output as-is."
                    ),
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        agent = create_openai_tools_agent(llm, tools, prompt)

        self.executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
        )

    async def run(self, message: str, session_id: str | None = None, **_kwargs):
        user_text = (message or "").strip()
        sid = session_id or "anonymous"  # or raise if you truly require it

        logger.info(
            "[StudentInfoTableAgent] run session_id=%s message=%r",
            sid,
            user_text[:200],
        )

        result: Any = await self.executor.ainvoke(
            {
                "input": user_text,
                "chat_history": [],  # TODO: wire real history if desired
            }
        )

        # AgentExecutor returns {"output": "...", "intermediate_steps": [...]}
        reply_text = ""
        intermediate_steps = []

        if isinstance(result, str):
            reply_text = result.strip()
        elif isinstance(result, dict):
            reply_text = (result.get("output") or "").strip()
            intermediate_steps = result.get("intermediate_steps") or []
        else:
            reply_text = str(result).strip()

        # FALLBACK 1: last tool observation
        if not reply_text and intermediate_steps:
            last_obs: Optional[Any] = None
            for _action, obs in intermediate_steps:
                last_obs = obs
            if last_obs is not None:
                reply_text = str(last_obs).strip()
                logger.info(
                    "[StudentInfoTableAgent] fallback: returning last tool observation (len=%s)",
                    len(reply_text),
                )

        # FALLBACK 2: ToolMessage edge case
        if not reply_text and isinstance(result, ToolMessage):
            reply_text = (result.content or "").strip()

        if not reply_text:
            reply_text = "No student information was returned."

        return AgentResult(
            answer_text=reply_text,
            intent="student_info",
            agent_id="student_info",
            agent_name=self.name,
            status="ok",
            extra_chunks=[],
            agent_session_id=sid,
            data={
                "raw_agent_result": result,
                "intermediate_steps_len": len(intermediate_steps) if intermediate_steps else 0,
            },
        )
