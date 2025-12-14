# src/OSSS/ai/agents/__init__.py
from __future__ import annotations

from typing import Dict, Type, Optional
import logging

from OSSS.ai.agents.base import AgentContext, AgentResult, Agent

# OSSS/ai/agents/__init__.py

from OSSS.ai.agents.registry import get_agent as get_handler_agent
from OSSS.ai.langchain.registry import get_langchain_agent as get_langchain_agent




logger = logging.getLogger("OSSS.ai.agents")

# Global registry: intent_name -> Agent class
_AGENT_REGISTRY: Dict[str, Type[Agent]] = {}


def get_agent(intent: str):
    """
    Returns either:
      - a normal (python) agent class/handler
      - or a LangChain agent (if aliased/registered)
      - or None (router will RAG-fallback)
    """
    # 1) Registry-based python agents (decorator)
    cls = _AGENT_REGISTRY.get(intent)
    if cls is not None:
        logger.info("Agent lookup intent=%s handler=True langchain=False (decorator registry)", intent)
        return cls

    # 2) Handler-based python agents (your other registry)
    handler = get_handler_agent(intent)
    if handler is not None:
        logger.info("Agent lookup intent=%s handler=True langchain=False (handler registry)", intent)
        return handler

    # 3) LangChain
    lc_agent = get_langchain_agent(intent)
    if lc_agent is not None:
        logger.info("Agent lookup intent=%s handler=False langchain=True", intent)
        return lc_agent

    logger.info("Agent lookup intent=%s handler=False langchain=False", intent)
    return None



def register_agent(intent_name: str):
    """
    Class decorator to register an Agent by intent_name.

    Usage:

        @register_agent("register_new_student")
        class RegisterNewStudentAgent:
            ...
    """
    def decorator(cls: Type[Agent]) -> Type[Agent]:
        name = intent_name or getattr(cls, "intent_name", None)
        if not name:
            raise ValueError(f"Agent {cls.__name__} must define an intent_name")

        if name in _AGENT_REGISTRY:
            logger.warning(
                "Overwriting agent for intent %s: %s -> %s",
                name,
                _AGENT_REGISTRY[name].__name__,
                cls.__name__,
            )

        _AGENT_REGISTRY[name] = cls
        logger.info("Registered agent intent=%s class=%s", name, cls.__name__)
        return cls

    return decorator



# ----------------------------------------------------------------------
# IMPORTANT: Import agent modules so their decorators execute
# ----------------------------------------------------------------------
# This ensures @register_agent(...) runs and the agent gets added
# to _AGENT_REGISTRY before router_agent calls get_agent().

try:
    from OSSS.ai.agents import registration as _registration_agent  # noqa: F401
    logger.info("Imported registration agent module")
except Exception as e:
    logger.error("Failed to import registration agent module: %s", e)


# Re-export base classes for convenient imports
from OSSS.ai.agents.base import AgentContext, AgentResult  # noqa: E402,F401


from OSSS.ai.agents.registry import list_agents
logger.info("Loaded agents: %s", list_agents())
