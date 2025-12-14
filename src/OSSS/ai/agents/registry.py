# src/OSSS/ai/agents/registry.py
from __future__ import annotations

from typing import Dict, Optional, Type, Callable, overload
from .base import Agent

_AGENT_REGISTRY: Dict[str, Type[Agent]] = {}

def _norm(intent: str) -> str:
    return (intent or "").strip().lower()

@overload
def register_agent(intent_name: str, agent_cls: Type[Agent]) -> None: ...
@overload
def register_agent(intent_name: str) -> Callable[[Type[Agent]], Type[Agent]]: ...

def register_agent(intent_name: str, agent_cls: Optional[Type[Agent]] = None):
    intent_key = _norm(intent_name)

    # decorator form
    if agent_cls is None:
        def deco(cls: Type[Agent]) -> Type[Agent]:
            _AGENT_REGISTRY[intent_key] = cls
            return cls
        return deco

    # direct call form
    _AGENT_REGISTRY[intent_key] = agent_cls
    return None

def get_agent(intent_name: str) -> Optional[Agent]:
    agent_cls = _AGENT_REGISTRY.get(_norm(intent_name))
    return agent_cls() if agent_cls else None

def list_agents() -> Dict[str, str]:
    return {k: v.__name__ for k, v in _AGENT_REGISTRY.items()}
