# src/OSSS/ai/langchain/agents/student_info_table_agent.py
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from OSSS.ai.langchain.base import LangChainAgentProtocol, get_llm
from OSSS.ai.langchain.tools.student_info_table_tool import student_info_table_tool

logger = logging.getLogger("OSSS.ai.langchain.student_info_table_agent")


class StudentInfoTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that uses the `student_info_table` StructuredTool.

    The LLM decides how to fill:
      - first_name_prefix
      - last_name_prefix
      - genders
      - grade_levels

    and the tool returns the filtered summary + markdown table.
    """

    name = "lc.student_info_table"

    def __init__(self) -> None:
        llm = get_llm()

        tools = [student_info_table_tool]

        # Tool-using prompt:
        # - ALWAYS call the tool at least once.
        # - Do NOT fabricate your own table; rely on the tool's markdown.
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
                        "- Use grade_levels=['THIRD'] etc. for grade-level filters.\n\n"
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
        self.executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the tools agent. The final natural-language reply comes from the LLM,
        based on the tool output. In most cases, it should surface the tool's
        markdown table directly.
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

        if isinstance(result, str):
            reply_text = result
        elif isinstance(result, dict):
            reply_text = result.get("output", "")
        else:
            reply_text = str(result)


        return {
            "reply": reply_text,
            "agent": self.name,
            "raw_agent_result": result,
        }
