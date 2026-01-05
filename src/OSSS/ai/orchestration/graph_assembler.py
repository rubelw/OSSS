from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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

        # ---- Entry point (pattern default, but allow execution_state override)
        entry = pattern.get_entry_point(agents) or agents[0]

        exec_state = inp.execution_state if isinstance(inp.execution_state, dict) else {}
        ec = exec_state.get("execution_config") if isinstance(exec_state.get("execution_config"), dict) else {}
        forced_entry = str(ec.get("entry_point") or "").strip().lower()
        if forced_entry:
            if forced_entry not in agents_set:
                raise GraphAssemblerError(
                    f"Forced entry_point '{forced_entry}' not in planned agents "
                    f"for pattern '{inp.pattern_name}': {sorted(agents_set)}"
                )
            entry = forced_entry

        graph.set_entry_point(entry)

        # ---- Conditional edges (router registry + pattern mappings)
        if getattr(pattern, "has_conditional", None) and pattern.has_conditional():
            self._add_conditional_edges(graph, pattern, agents, inp.pattern_name)

        # ---- Base edges from pattern
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
            # If NodeRegistry.available() is not present or fails, we degrade to probing.
            available = set()

        if available:
            missing = sorted(set(agents) - available)
            if missing:
                raise GraphAssemblerError(
                    f"Missing node(s) for pattern '{pattern_name}': {', '.join(missing)}. "
                    f"Available: {', '.join(sorted(available))}"
                )
            return

        # Fallback: attempt to resolve each node; any failure is missing.
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

            dest_map: Dict[str, Any] = {"END": END}

            get_dests = getattr(pattern, "resolve_conditional_destinations_for", None)
            if callable(get_dests):
                for k, dest in (get_dests(from_node, agents) or {}).items():
                    if not k:
                        continue

                    if isinstance(dest, str) and dest.strip().lower() == "end":
                        dest_map[str(k)] = END
                        continue

                    d = str(dest).strip().lower()
                    if d in agents_set:
                        dest_map[str(k)] = d
                    else:
                        # We intentionally ignore unknown destinations to keep patterns flexible,
                        # but you can uncomment the next line to hard-fail instead.
                        # raise GraphAssemblerError(f"Conditional dest '{d}' not in agents for pattern '{pattern_name}'")
                        pass

            graph.add_conditional_edges(from_node, router_fn, dest_map)

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
