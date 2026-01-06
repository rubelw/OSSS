from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from langgraph.graph import StateGraph, END

from OSSS.ai.orchestration.state_schemas import OSSSState, OSSSContext
from OSSS.ai.observability import get_logger

# ✅ spec.py no longer owns RouterRegistry (router names only)
from .patterns.spec import GraphPattern

# ✅ canonical runtime router registry
from .routers.registry import RouterRegistry

from .node_registry import NodeRegistry


class GraphAssemblerError(Exception):
    pass


@dataclass(frozen=True)
class AssembleInput:
    pattern_name: str
    agents: List[str]
    execution_state: Optional[Dict[str, Any]] = None


class GraphAssembler:
    """
    Owns ALL graph mutation:
      - add_node
      - add_edge
      - add_conditional_edges
      - set_entry_point

    Also owns validation of requested nodes/edges/routers for a permanent contract:
      - If a node is requested but not registered -> fail fast
      - If an edge references an unknown node -> fail fast
      - If a pattern requires a router not registered -> fail fast

    Best-practice hardening (NEW):
      - Conditional routers are wrapped so that:
          * router exceptions never crash the graph (fallback branch)
          * non-str router outputs are clamped
          * invalid branch keys are clamped to a deterministic fallback
        This prevents “turn 2” / resume flows from being derailed by runtime router issues.
    """

    def __init__(self, *, nodes: NodeRegistry, routers: RouterRegistry) -> None:
        self.logger = get_logger(f"{__name__}.GraphAssembler")
        self.nodes = nodes
        self.routers = routers

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------

    def assemble(self, pattern: GraphPattern, inp: AssembleInput) -> StateGraph[OSSSState]:
        agents = [str(a).strip().lower() for a in (inp.agents or []) if a]
        if not agents:
            raise GraphAssemblerError("No agents provided to GraphAssembler.assemble()")

        # ✅ Permanent fix: validate requested nodes BEFORE mutating graph
        self._validate_requested_nodes(agents, inp.pattern_name)

        agents_set = set(agents)
        graph = StateGraph[OSSSState](state_schema=OSSSState, context_schema=OSSSContext)

        # ---- Nodes
        for name in agents:
            graph.add_node(name, self.nodes.get(name))

        # ---- Entry point
        # Fix 2: GraphFactory may have overridden pattern.entry_point per-run.
        entry = pattern.get_entry_point(agents) or agents[0]
        entry = str(entry).strip().lower()

        if entry not in agents_set:
            raise GraphAssemblerError(
                f"Pattern '{inp.pattern_name}' resolved entry_point '{entry}' not in planned agents: {sorted(agents_set)}"
            )

        graph.set_entry_point(entry)

        # ---- Conditional edges (router registry + pattern mappings)
        if getattr(pattern, "has_conditional", None) and pattern.has_conditional():
            self._add_conditional_edges(graph, pattern, agents, inp.pattern_name)

        # ---- Base edges from pattern (already filtered to agent set by GraphPattern)
        edges: List[Dict[str, str]] = pattern.resolve_edges(agents) or []
        self._assert_edges_valid(edges, agents, inp.pattern_name)

        for e in edges:
            frm = str(e["from"]).strip().lower()
            to_raw = str(e["to"]).strip()
            to_norm = to_raw.strip().lower()

            dest = END if to_norm == "end" else to_norm
            graph.add_edge(frm, dest)

        return graph

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def _validate_requested_nodes(self, agents: List[str], pattern_name: str) -> None:
        """
        Fail fast if a requested agent/node is not registered.
        This prevents downstream AttributeErrors and makes the contract explicit.
        """
        available = set()
        try:
            available = set(self.nodes.available())
        except Exception:
            available = set()

        if available:
            missing = sorted(set(agents) - available)
            if missing:
                raise GraphAssemblerError(
                    f"Missing node(s) for pattern '{pattern_name}': {', '.join(missing)}. "
                    f"Available: {', '.join(sorted(available))}"
                )
            return

        missing: List[str] = []
        for a in agents:
            try:
                _ = self.nodes.get(a)
            except Exception:
                missing.append(a)

        if missing:
            raise GraphAssemblerError(
                f"Missing node(s) for pattern '{pattern_name}': {', '.join(sorted(set(missing)))}"
            )

    # ------------------------------------------------------------------
    # ROUTER WRAPPING (BEST PRACTICE)
    # ------------------------------------------------------------------

    def _wrap_router_for_edge(
        self,
        *,
        router_name: str,
        router_fn: Callable[[OSSSState], str],
        from_node: str,
        allowed_keys: set[str],
        fallback: str,
        pattern_name: str,
    ) -> Callable[[OSSSState], str]:
        """
        Best-practice:
        - never let a router exception break execution
        - ensure router output is a valid branch key for THIS edge
        """
        allowed_keys = set(allowed_keys)
        if fallback not in allowed_keys and allowed_keys:
            # deterministic: pick a stable fallback if caller gave a bad one
            fallback = sorted(allowed_keys)[0]

        def _wrapped(state: OSSSState) -> str:
            try:
                out = router_fn(state)
                if not isinstance(out, str):
                    self.logger.error(
                        "router_return_non_string",
                        extra={
                            "event": "router_return_non_string",
                            "pattern": pattern_name,
                            "from_node": from_node,
                            "router": router_name,
                            "out_type": type(out).__name__,
                        },
                    )
                    return fallback

                key = out.strip()
                if key in allowed_keys:
                    return key

                self.logger.error(
                    "router_invalid_output_for_edge",
                    extra={
                        "event": "router_invalid_output_for_edge",
                        "pattern": pattern_name,
                        "from_node": from_node,
                        "router": router_name,
                        "out": key,
                        "allowed": sorted(allowed_keys),
                        "fallback": fallback,
                    },
                )
                return fallback
            except Exception as exc:
                self.logger.error(
                    "router_exception_clamped",
                    exc_info=True,
                    extra={
                        "event": "router_exception_clamped",
                        "pattern": pattern_name,
                        "from_node": from_node,
                        "router": router_name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "fallback": fallback,
                    },
                )
                return fallback

        return _wrapped

    # ------------------------------------------------------------------
    # CONDITIONAL EDGES
    # ------------------------------------------------------------------

    def _add_conditional_edges(
        self,
        graph: Any,
        pattern: GraphPattern,
        agents: List[str],
        pattern_name: str,
    ) -> None:
        agents_set = {a.lower() for a in agents}
        conditional = getattr(pattern, "conditional_edges", None) or {}

        for from_node, router_name in conditional.items():
            from_node = (from_node or "").strip().lower()
            if not from_node or from_node not in agents_set:
                continue

            router_name = str(router_name or "").strip()
            if not router_name:
                raise GraphAssemblerError(
                    f"Pattern '{pattern_name}' has conditional edge from '{from_node}' "
                    "but router_name is empty"
                )

            # ✅ Permanent fix: fail fast if router missing
            try:
                router_fn = self.routers.get(router_name)
            except Exception as e:
                raise GraphAssemblerError(
                    f"Pattern '{pattern_name}' requires router '{router_name}' "
                    f"for from_node '{from_node}', but it is not registered"
                ) from e

            # Destinations are already filtered to the planned agent set by GraphPattern.
            # Translate "END" -> END for LangGraph.
            dest_map: Dict[str, Any] = {}

            get_dests = getattr(pattern, "resolve_conditional_destinations_for", None)
            if callable(get_dests):
                raw_map = get_dests(from_node, agents) or {}
            else:
                raw_map = {}

            for k, dest in raw_map.items():
                if not k:
                    continue
                d = str(dest or "").strip()
                if not d:
                    continue
                if d.strip().lower() == "end":
                    dest_map[str(k)] = END
                else:
                    dn = d.strip().lower()
                    if dn in agents_set:
                        dest_map[str(k)] = dn

            # Optional default end mapping (safe no-op unless routers emit "END")
            dest_map.setdefault("END", END)

            # ✅ BEST PRACTICE: wrap router so it can't crash execution or return invalid keys.
            allowed_keys = set(dest_map.keys())
            fallback_key = "END" if "END" in allowed_keys else (sorted(allowed_keys)[0] if allowed_keys else "END")
            safe_router_fn = self._wrap_router_for_edge(
                router_name=router_name,
                router_fn=router_fn,
                from_node=from_node,
                allowed_keys=allowed_keys,
                fallback=fallback_key,
                pattern_name=pattern_name,
            )

            graph.add_conditional_edges(from_node, safe_router_fn, dest_map)

    # ------------------------------------------------------------------
    # EDGE VALIDATION
    # ------------------------------------------------------------------

    def _assert_edges_valid(self, edges: List[Dict[str, str]], agents: List[str], pattern_name: str) -> None:
        agents_set = {a.lower() for a in agents}
        for e in edges:
            frm = str(e.get("from", "")).strip().lower()
            to = str(e.get("to", "")).strip().lower()
            if not frm or not to:
                continue
            if frm != "end" and frm not in agents_set:
                raise GraphAssemblerError(f"Invalid edge from '{frm}' in pattern '{pattern_name}'")
            if to != "end" and to not in agents_set:
                raise GraphAssemblerError(f"Invalid edge to '{to}' in pattern '{pattern_name}'")
