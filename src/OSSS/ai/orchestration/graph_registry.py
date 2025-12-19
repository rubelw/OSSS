# graph_registry.py
from dataclasses import dataclass
from typing import Dict, Optional
from OSSS.ai.observability import get_logger

WILDCARD = "*"
logger = get_logger(__name__)

@dataclass(frozen=True)
class RouteKey:
    action: str = WILDCARD
    intent: str = WILDCARD
    tone: str = WILDCARD
    sub_intent: str = WILDCARD


class GraphRegistry:
    def __init__(self) -> None:
        self._routes: Dict[RouteKey, str] = {}

    def register(self, key: RouteKey, graph_id: str) -> None:
        self._routes[key] = graph_id
        logger.debug(
            "Graph route registered",
            extra={"route_key": key, "graph_id": graph_id, "route_count": len(self._routes)},
        )

    def resolve(self, decision: Optional[dict]) -> str:
        if not isinstance(decision, dict):
            logger.warning(
                "Graph resolve called with invalid decision; using default",
                extra={
                    "decision_type": type(decision).__name__,
                    "decision_preview": str(decision)[:200] if decision is not None else None,
                },
            )
            return "graph_default"

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

        logger.info(
            "Resolving graph",
            extra={
                "decision": {"action": a, "intent": i, "tone": t, "sub_intent": s},
                "candidate_keys": candidates,
                "route_count": len(self._routes),
            },
        )

        for idx, k in enumerate(candidates):
            if k in self._routes:
                graph_id = self._routes[k]
                logger.info(
                    "Graph resolved",
                    extra={
                        "matched_index": idx,
                        "matched_key": k,
                        "selected_graph": graph_id,
                        "decision": {"action": a, "intent": i, "tone": t, "sub_intent": s},
                    },
                )
                return graph_id

            logger.debug(
                "Graph candidate miss",
                extra={"candidate_index": idx, "candidate_key": k},
            )

        logger.warning(
            "Graph resolve fell through; using graph_default",
            extra={"decision": {"action": a, "intent": i, "tone": t, "sub_intent": s}},
        )
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
