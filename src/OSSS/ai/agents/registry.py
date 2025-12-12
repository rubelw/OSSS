# src/OSSS/ai/agents/registry.py
from __future__ import annotations

from typing import Dict, Optional, Type

from .base import Agent, AgentContext, AgentResult

import logging

logger = logging.getLogger("OSSS.ai.agents.registry")

# ======================================================================
# GLOBAL AGENT REGISTRY
# ======================================================================
# This is a simple in-process dictionary that maps:
#       intent_name (str)  --->  Agent class (subclass of Agent Protocol)
#
# Why a global registry?
# ----------------------
# - It enables a plugin-like system where agents automatically register
#   themselves at import time.
# - The orchestrator can dynamically look up an agent implementation
#   using only the intent string.
# - Agents can be conditionally loaded or swapped without modifying the
#   orchestrator or router code.
#
# Limitations
# -----------
# - Not safe for a multi-process distributed environment unless each
#   worker loads agents deterministically and identically. That’s fine,
#   because this registry is intentionally designed for in-process agent
#   routing, not cross-node service discovery.
# - Not persistent across restarts (again: by design).
#
# For future expansion:
# - Could be extended to support multiple agents per intent.
# - Could register agents by capabilities or tags.
#
_AGENT_REGISTRY: Dict[str, Type[Agent]] = {}


# ======================================================================
# register_agent
# ======================================================================
def register_agent(intent_name: str, agent_cls: Type[Agent]) -> None:
    """
    Register an agent class in the global registry.

    This is the *primary mechanism* by which new agents become discoverable.

    Typical usage patterns
    ----------------------
    1. Direct call:
        register_agent("register_new_student", RegisterNewStudentAgent)

    2. Decorator usage (recommended):
        @register_agent("register_new_student")
        class RegisterNewStudentAgent:
            ...

    The decorator syntax allows agents to self-register upon import,
    which is extremely convenient for plugin-style architectures.

    Parameters
    ----------
    intent_name : str
        Unique logical name of the agent (e.g., "register_new_student").
        Must be globally unique across the agent ecosystem.

    agent_cls : Type[Agent]
        The agent implementation class.
        Should implement the Agent Protocol (i.e., async run()).

    Behavior
    --------
    - If an agent for this intent already exists, it will be overwritten.
      (This allows hot-swapping in testing environments.)
    """
    _AGENT_REGISTRY[intent_name] = agent_cls


# ======================================================================
# get_agent
# ======================================================================
def get_agent(intent_name: str) -> Optional[Agent]:
    """
    Retrieve a *NEW INSTANCE* of the agent class registered for this intent.

    Why return a NEW instance each time?
    -----------------------------------
    - Agents are expected to be stateless, except for subagent "session"
      state which is stored externally (Redis, DB, in-memory store, etc).
    - Creating a fresh instance avoids any chance of shared mutable state
      across requests.
    - It allows different invocations of the same agent to run concurrently
      without interfering.

    Returns
    -------
    Agent instance or None
        - If no agent is registered for the intent, returns None.
        - Otherwise instantiates the agent with no constructor arguments.
          (If the agent needs dependencies, use dependency injection in
           the agent's __init__ with defaults.)

    Notes
    -----
    - `type: ignore[call-arg]` is used because Python's static typing
      cannot guarantee the agent constructor takes no arguments.
      In practice, we ensure this manually.
    """
    agent_cls = _AGENT_REGISTRY.get(intent_name)
    if agent_cls is None:
        return None

    # Instantiate a fresh agent instance each time
    return agent_cls()  # type: ignore[call-arg]


# ======================================================================
# list_agents
# ======================================================================
def list_agents() -> Dict[str, str]:
    """
    Return a simplified introspection view of the registry.

    Useful for:
        - unit tests (to ensure all expected agents are loaded)
        - debugging in interactive REPL environments
        - developer tooling (IDE agent browsers, admin dashboards)

    Returns
    -------
    Dict[str, str]
        Mapping of:
            intent_name -> class_name
    """
    return {k: v.__name__ for k, v in _AGENT_REGISTRY.items()}
