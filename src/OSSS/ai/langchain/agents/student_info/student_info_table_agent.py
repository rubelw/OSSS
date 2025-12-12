# src/OSSS/ai/langchain/agents/student_info_table_agent.py
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage

from OSSS.ai.langchain.base import LangChainAgentProtocol, get_llm
from OSSS.ai.langchain.tools.student_info.student_info_table_tool import student_info_table_tool

logger = logging.getLogger("OSSS.ai.langchain.student_info_table_agent")


class StudentInfoTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that uses the `student_info_table` StructuredTool.

    The LLM decides how to fill:
      - first_name_prefix
      - last_name_prefix
      - genders
      - grade_levels
      - enrolled_only

    and the tool returns the filtered summary + markdown table.
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

        # IMPORTANT:
        # - return_intermediate_steps=True lets us recover tool output even if the LLM
        #   fails to produce a final natural-language response.
        self.executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
        )

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the tools agent.

        If the LLM fails to produce a final answer (common failure mode: it emits a tool call
        but doesn't surface the tool result), we fall back to returning the last tool output
        from intermediate_steps.
        """
        logger.info(
            "[StudentInfoTableAgent] Running with message=%r session_id=%r",
            message,
            session_id,
        )

        result = await self.executor.ainvoke(
            {
                "input": message,
                "chat_history": [],  # you can thread real history later if you want
            }
        )

        # Normal case: AgentExecutor returns {"output": "...", "intermediate_steps": [...]}
        reply_text = ""
        intermediate_steps = []

        if isinstance(result, str):
            reply_text = result
        elif isinstance(result, dict):
            reply_text = (result.get("output") or "").strip()
            intermediate_steps = result.get("intermediate_steps") or []
        else:
            reply_text = str(result)

        # FALLBACK:
        # If the model didn't produce a final output, but tools ran, return the last tool output.
        # intermediate_steps format: List[Tuple[AgentAction, observation]]
        if not reply_text and intermediate_steps:
            last_obs = None
            for _action, obs in intermediate_steps:
                last_obs = obs
            if last_obs is not None:
                reply_text = str(last_obs).strip()
                logger.info(
                    "[StudentInfoTableAgent] fallback: returning last tool observation (len=%s)",
                    len(reply_text),
                )

        # LAST RESORT:
        # Some buggy runs produce a ToolMessage-like object; handle that too.
        if not reply_text and isinstance(result, ToolMessage):
            reply_text = (result.content or "").strip()

        return {
            "reply": reply_text,
            "agent": self.name,
            "raw_agent_result": result,
        }
