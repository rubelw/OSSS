from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from OSSS.ai.observability import get_logger

from OSSS.ai.orchestration.node_wrappers import (
    refiner_node,
    data_query_node,
    critic_node,
    historian_node,
    synthesis_node,
    final_node,
)
from OSSS.ai.orchestration.nodes.validator_node import ValidatorNode
from OSSS.ai.orchestration.nodes.terminator_node import TerminatorNode
from OSSS.ai.orchestration.nodes.aggregator_node import AggregatorNode
from OSSS.ai.orchestration.nodes.decision_node import DecisionNode


class NodeRegistryError(Exception):
    pass


@dataclass(frozen=True)
class NodeRegistryConfig:
    # Future: feature flags / optional nodes, etc.
    pass


class NodeRegistry:
    """
    Owns agent-name -> node callable mapping.
    """

    def __init__(self, cfg: Optional[NodeRegistryConfig] = None) -> None:
        self.logger = get_logger(f"{__name__}.NodeRegistry")
        self.cfg = cfg or NodeRegistryConfig()
        self._nodes: Dict[str, Any] = {
            "refiner": refiner_node,
            "data_query": data_query_node,
            "critic": critic_node,
            "historian": historian_node,
            "synthesis": synthesis_node,
            "validator": ValidatorNode,
            "terminator": TerminatorNode,
            "aggregator": AggregatorNode,
            "decision": DecisionNode,
            "final": final_node,
        }

    def has(self, name: str) -> bool:
        return (name or "").strip().lower() in self._nodes

    def get(self, name: str) -> Any:
        key = (name or "").strip().lower()
        if key not in self._nodes:
            raise NodeRegistryError(f"Unknown agent: {name}")
        return self._nodes[key]

    def available(self) -> set[str]:
        return set(self._nodes.keys())
