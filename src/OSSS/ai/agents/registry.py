# src/OSSS/ai/agents/registry.py
from __future__ import annotations

from typing import Dict, Optional, Type

from .base import Agent, AgentContext, AgentResult

# Simple in-process registry keyed by intent name
_AGENT_REGISTRY: Dict[str, Type[Agent]] = {}


def register_agent(intent_name: str, agent_cls: Type[Agent]) -> None:
    """
    Register an agent class for a given intent_name.
    Example:
        register_agent(RegisterNewStudentAgent.intent_name, RegisterNewStudentAgent)
    """
    _AGENT_REGISTRY[intent_name] = agent_cls


def get_agent(intent_name: str) -> Optional[Agent]:
    """
    Return a NEW instance of the agent for this intent, if registered.
    """
    agent_cls = _AGENT_REGISTRY.get(intent_name)
    if agent_cls is None:
        return None
    return agent_cls()  # type: ignore[call-arg]


def list_agents() -> Dict[str, str]:
    """
    For debugging: returns a mapping of intent_name -> class_name.
    """
    return {k: v.__name__ for k, v in _AGENT_REGISTRY.items()}
