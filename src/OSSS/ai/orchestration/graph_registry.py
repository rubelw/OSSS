# graph_registry.py
from dataclasses import dataclass
from typing import Dict, Optional
from OSSS.ai.observability import get_logger

WILDCARD = "*"
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Gate configuration
# ---------------------------------------------------------------------------

DATAVIEW_TRIGGER_WORD = "query"

# Treat "query ..." as a dataview request for any read/write-ish operation.
# Includes synonyms used by the LLM layer.
DATAVIEW_ACTIONS = {
    "read",
    "create",
    "add",
    "update",
    "edit",
    "delete",
    # optional: if you treat routing requests containing "query" as dataview too
    "route",
}

# Keep action normalization here so the registry is robust even if upstream changes.
ACTION_NORMALIZATION = {
    "add": "create",
    "edit": "update",
}

def normalize_action(action: object) -> str:
    if not isinstance(action, str) or not action.strip():
        return WILDCARD
    a = action.strip().lower()
    return ACTION_NORMALIZATION.get(a, a)


@dataclass(frozen=True)
class RouteKey:
    action: str = WILDCARD
    intent: str = WILDCARD
    tone: str = WILDCARD
    sub_intent: str = WILDCARD

    def to_dict(self) -> dict:
        """
        Convert the RouteKey to a dictionary for JSON serialization.
        This will make it serializable and ready for logging.
        """
        return {
            "action": self.action,
            "intent": self.intent,
            "tone": self.tone,
            "sub_intent": self.sub_intent,
        }

    def __str__(self) -> str:
        """
        String representation for logging purposes.
        """
        return f"RouteKey(action={self.action}, intent={self.intent}, tone={self.tone}, sub_intent={self.sub_intent})"


class GraphRegistry:
    def __init__(self) -> None:
        self._routes: Dict[RouteKey, str] = {}

    def register(self, key: RouteKey, graph_id: str) -> None:
        self._routes[key] = graph_id
        logger.debug(
            "Graph route registered",
            extra={"route_key": key.to_dict(), "graph_id": graph_id, "route_count": len(self._routes)},
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

        # Normalize action so registry keys are stable
        a = normalize_action(decision.get("action", WILDCARD))
        i = decision.get("intent", WILDCARD)
        t = decision.get("tone", WILDCARD)
        s = decision.get("sub_intent", WILDCARD)

        # -----------------------------------------------------------------------
        # Workflow-based gate (runs BEFORE content/table routing)
        # NOTE: In your logs, decision["workflow_id"] is a UUID execution/workflow id,
        # not the slug "data-views-demo". So we look for slug/name-style keys too.
        # -----------------------------------------------------------------------
        meta = (
                decision.get("execution_metadata")
                or decision.get("metadata")
                or decision.get("meta")
                or {}
        )
        if not isinstance(meta, dict):
            meta = {}

        workflow_selector = (
                decision.get("selected_workflow_id")
                or decision.get("workflow_slug")
                or decision.get("workflow_name")
                or decision.get("workflow_key")
                or decision.get("workflow")
                or meta.get("selected_workflow_id")
                or meta.get("workflow_slug")
                or meta.get("workflow_name")
                or meta.get("workflow_key")
                or meta.get("workflow")
                or ""
        )

        logger.debug(
            "Graph resolve workflow selectors",
            extra={
                "workflow_selector": str(workflow_selector),
                "decision_workflow_id": str(decision.get("workflow_id", "")),
                "decision_selected_workflow_id": str(decision.get("selected_workflow_id", "")),
                "meta_workflow_slug": str(meta.get("workflow_slug", "")),
                "meta_selected_workflow_id": str(meta.get("selected_workflow_id", "")),
            },
        )

        if str(workflow_selector) == "data-views-demo":
            logger.info(
                "Graph gated to data views by workflow selector",
                extra={
                    "selected_graph": "graph_data_views",
                    "workflow_selector": str(workflow_selector),
                    "decision": {"action": a, "intent": i, "tone": t, "sub_intent": s},
                },
            )
            return "graph_data_views"

        # Content-based gate (runs BEFORE table routing)
        query_text = (decision.get("query_text") or decision.get("query") or "")
        query_text_lc = str(query_text).lower()

        if a in DATAVIEW_ACTIONS and DATAVIEW_TRIGGER_WORD in query_text_lc:
            logger.info(
                "Graph gated to data views by content trigger",
                extra={
                    "selected_graph": "graph_data_views",
                    "trigger_word": DATAVIEW_TRIGGER_WORD,
                    "action": a,
                    "decision": {"action": a, "intent": i, "tone": t, "sub_intent": s},
                },
            )
            return "graph_data_views"

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

            logger.debug("Graph candidate miss", extra={"candidate_index": idx, "candidate_key": k})

        logger.warning(
            "Graph resolve fell through; using graph_default",
            extra={"decision": {"action": a, "intent": i, "tone": t, "sub_intent": s}},
        )
        return "graph_default"


GRAPH_REGISTRY = GraphRegistry()

# Troubleshooting
GRAPH_REGISTRY.register(RouteKey(action="troubleshoot"), "graph_diagnostics")

# Creation / writing (covers both "create" and "add" after normalization)
GRAPH_REGISTRY.register(RouteKey(action="create"), "graph_builder")

# Calm angry explanations (tone taxonomy updated: "angry" -> "critical")
GRAPH_REGISTRY.register(RouteKey(action="explain", tone="critical"), "graph_explain_deescalate")

# Read + data
GRAPH_REGISTRY.register(RouteKey(action="read", sub_intent="data_query"), "graph_data_read")

# Absolute fallback
GRAPH_REGISTRY.register(RouteKey(), "graph_default")

