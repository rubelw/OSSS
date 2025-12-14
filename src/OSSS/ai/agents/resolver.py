# src/OSSS/ai/agents/resolver.py
from OSSS.ai.agents.registry import get_agent as get_handler_agent
from OSSS.ai.langchain.registry import get_agent as get_langchain_agent  # adjust import

def resolve_agent(intent: str):
    return get_handler_agent(intent) or get_langchain_agent(intent)
