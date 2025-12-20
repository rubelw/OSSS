from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class GraphEdgeSpec:
    from_node: str
    to_node: str
    # For non-conditional edges, condition_key is None
    condition_key: Optional[str] = None  # e.g. "allow", "format_block", etc.


@dataclass(frozen=True)
class GraphSpec:
    """
    Declarative spec describing the graph to compile.

    IMPORTANT:
    - This should be fully “decided” and policy-enforced.
    - GraphFactory should not mutate it.
    """
    pattern_name: str
    nodes: List[str]  # ordered node ids to add
    entry_point: str
    edges: Tuple[GraphEdgeSpec, ...] = ()
    conditional_edges: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # conditional_edges[from_node] = {condition_key: to_node, ...}
    metadata: Dict[str, Any] = field(default_factory=dict)

    def cache_key(self) -> Tuple[Any, ...]:
        """A stable cache key for compiled graphs."""
        return (
            self.pattern_name,
            tuple(self.nodes),
            self.entry_point,
            tuple((e.from_node, e.to_node, e.condition_key) for e in self.edges),
            tuple(
                (src, tuple(sorted(routes.items())))
                for src, routes in sorted(self.conditional_edges.items())
            ),
        )
