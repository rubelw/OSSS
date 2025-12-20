from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

from OSSS.ai.langgraph_backend.graph_spec import GraphSpec, GraphEdgeSpec
from OSSS.ai.langgraph_backend.graph_patterns import PatternRegistry

# Keep normalization in ONE place (builder)
NORMALIZE = {
    "data_view": "data_views",
    "data_views": "data_views",
}

GUARD_REQUIRED = ["answer_search", "format_response"]
GUARD_OPTIONAL = ["format_block", "format_requires_confirmation"]


def _norm(name: str) -> str:
    n = (name or "").strip().lower()
    return NORMALIZE.get(n, n)


def _dedupe(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _enforce_guard_pipeline(nodes: List[str], allow_auto_inject_nodes: bool) -> List[str]:
    """
    Policy: Guard pipeline MUST be explicit unless allow_auto_inject_nodes=True.
    Guard must be first if present.
    """
    nodes = [_norm(n) for n in nodes]
    nodes = _dedupe(nodes)

    if "guard" not in nodes:
        return nodes

    missing_required = [n for n in GUARD_REQUIRED if n not in nodes]
    missing_optional = [n for n in GUARD_OPTIONAL if n not in nodes]

    if (missing_required or missing_optional) and not allow_auto_inject_nodes:
        raise ValueError(
            "Guard pipeline incomplete and auto-inject disabled. "
            f"missing_required={missing_required}, missing_optional={missing_optional}"
        )

    if allow_auto_inject_nodes:
        for n in GUARD_REQUIRED + GUARD_OPTIONAL:
            if n not in nodes:
                nodes.append(n)

    # Guard must be first
    nodes = ["guard"] + [n for n in nodes if n != "guard"]
    return _dedupe(nodes)


def build_spec(
    *,
    plan,  # your planning.ExecutionPlan (duck-typed)
    pattern_registry: Optional[PatternRegistry] = None,
) -> GraphSpec:
    """
    Convert an ExecutionPlan into a GraphSpec.
    All policy enforcement happens here.
    """
    pattern_registry = pattern_registry or PatternRegistry()
    pattern_name = getattr(plan, "pattern_name", "standard")
    allow_auto = bool(getattr(plan, "allow_auto_inject_nodes", False))

    agents = [_norm(a) for a in (getattr(plan, "agents_to_run", []) or [])]
    agents = _dedupe(agents)
    agents = _enforce_guard_pipeline(agents, allow_auto_inject_nodes=allow_auto)
    agents = _dedupe([_norm(a) for a in agents])

    # Guard spec is explicit (no factory “magic”)
    if "guard" in agents:
        # entry is guard
        entry_point = "guard"

        # Conditional routing from guard -> 3 targets
        conditional_edges = {
            "guard": {
                "allow": "answer_search",
                "requires_confirmation": "format_requires_confirmation",
                "block": "format_block",
            }
        }

        # Linear edges after guard routing
        edges = []

        # Decide presence of data_views and synthesis
        has_data = "data_views" in agents
        has_synth = "synthesis" in agents

        if has_data:
            if has_synth:
                edges.append(GraphEdgeSpec("answer_search", "synthesis"))
                edges.append(GraphEdgeSpec("synthesis", "data_views"))
            else:
                edges.append(GraphEdgeSpec("answer_search", "data_views"))
            edges.append(GraphEdgeSpec("data_views", "format_response"))
        else:
            edges.append(GraphEdgeSpec("answer_search", "format_response"))

        # Terminal edges (GraphFactory will map to END)
        edges.append(GraphEdgeSpec("format_response", "END"))
        edges.append(GraphEdgeSpec("format_block", "END"))
        edges.append(GraphEdgeSpec("format_requires_confirmation", "END"))

        return GraphSpec(
            pattern_name=pattern_name,
            nodes=agents,
            entry_point=entry_point,
            edges=tuple(edges),
            conditional_edges=conditional_edges,
            metadata={
                "source": "build_spec",
                "allow_auto_inject_nodes": allow_auto,
                "mode": "guard_pipeline",
            },
        )

    # Non-guard graphs: use pattern registry to compute edges/entry
    pattern = pattern_registry.get_pattern(pattern_name)
    if not pattern:
        raise ValueError(f"Unknown graph pattern: {pattern_name}")

    entry = pattern.get_entry_point(agents) or (agents[0] if agents else "")
    pattern_edges = pattern.get_edges(agents)  # list of {"from","to"}

    edges = tuple(GraphEdgeSpec(e["from"], e["to"]) for e in pattern_edges)

    return GraphSpec(
        pattern_name=pattern_name,
        nodes=agents,
        entry_point=entry,
        edges=edges,
        conditional_edges={},
        metadata={
            "source": "build_spec",
            "allow_auto_inject_nodes": allow_auto,
            "mode": "pattern",
        },
    )
