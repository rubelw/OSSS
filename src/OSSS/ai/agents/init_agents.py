# OSSS/ai/init_agents.py
from OSSS.ai.agents.registry import register_agent
from OSSS.ai.langchain.adapter import LangChainAgentAdapter
from OSSS.ai.langchain.some_agent import default_chat_agent
from OSSS.ai.some_handler_agent import StaffDirectoryAgent

def init_agents() -> None:
    register_agent(LangChainAgentAdapter(default_chat_agent))
    register_agent(StaffDirectoryAgent())  # must have .name and async run()
