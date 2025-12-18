from dataclasses import dataclass
from typing import Dict

WILDCARD = "*"


@dataclass(frozen=True)
class RouteKey:
    action: str = WILDCARD
    intent: str = WILDCARD
    tone: str = WILDCARD
    sub_intent: str = WILDCARD


class GraphRegistry:
    """
    Maps (action, intent, tone, sub_intent) → graph_id
    Supports wildcard fallback matching.
    """

    def __init__(self) -> None:
        self._routes: Dict[RouteKey, str] = {}

    def register(self, key: RouteKey, graph_id: str) -> None:
        self._routes[key] = graph_id

    def resolve(self, decision: dict) -> str:
        a = decision.get("action", WILDCARD)
        i = decision.get("intent", WILDCARD)
        t = decision.get("tone", WILDCARD)
        s = decision.get("sub_intent", WILDCARD)

        candidates = [
            RouteKey(a, i, t, s),
            RouteKey(a, i, t, WILDCARD),
            RouteKey(a, i, WILDCARD, s),
            RouteKey(a, i, WILDCARD, WILDCARD),
            RouteKey(a, WILDCARD, WILDCARD, WILDCARD),
            RouteKey(WILDCARD, i, WILDCARD, WILDCARD),
            RouteKey(WILDCARD, WILDCARD, WILDCARD, WILDCARD),
        ]

        for k in candidates:
            if k in self._routes:
                return self._routes[k]

        return "graph_default"


GRAPH_REGISTRY = GraphRegistry()

# Troubleshooting
GRAPH_REGISTRY.register(RouteKey(action="troubleshoot"), "graph_diagnostics")

# Creation / writing
GRAPH_REGISTRY.register(RouteKey(action="create"), "graph_builder")

# Calm angry explanations
GRAPH_REGISTRY.register(RouteKey(action="explain", tone="angry"), "graph_explain_deescalate")

# Read + data
GRAPH_REGISTRY.register(RouteKey(action="read", sub_intent="data_query"), "graph_data_read")

# Absolute fallback
GRAPH_REGISTRY.register(RouteKey(), "graph_default")
