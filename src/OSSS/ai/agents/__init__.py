# src/OSSS/ai/agents/__init__.py
from __future__ import annotations

from typing import Dict, Type, Optional
import logging

from OSSS.ai.agents.base import AgentContext, AgentResult, Agent

logger = logging.getLogger("OSSS.ai.agents")

# Global registry: intent_name -> Agent class
_AGENT_REGISTRY: Dict[str, Type[Agent]] = {}


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


def get_agent(intent_name: str) -> Optional[Agent]:
    """
    Look up an agent by intent_name and return an *instance*.

    This is what your router/orchestrator should call.
    """
    cls = _AGENT_REGISTRY.get(intent_name)
    if not cls:
        logger.info("No agent registered for intent=%s", intent_name)
        return None
    return cls()  # type: ignore[call-arg]


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
