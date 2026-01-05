"""
Routing interfaces / base types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from OSSS.ai.context import AgentContext


class RoutingFunction(ABC):
    """
    Common router interface for LangGraph conditional edges.
    """

    @abstractmethod
    def __call__(self, context: AgentContext) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_possible_targets(self) -> List[str]:
        raise NotImplementedError
