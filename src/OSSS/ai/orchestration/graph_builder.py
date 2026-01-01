"""
Graph builder for converting OSSS agents to LangGraph structures.

This module provides utilities to build LangGraph-compatible graphs from
OSSS agent definitions, including:
- node creation from agents
- edge routing (dependencies + custom routing)
- graph validation (missing nodes, cycles, entry/exit points)
- a lightweight executor to simulate graph execution (sanity testing)

Important conceptual mapping:
- A OSSS "agent" becomes a LangGraph "node"
- Dependencies between agents become directed edges
- The result is intended to be a DAG (Directed Acyclic Graph)
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Set

from pydantic import BaseModel, Field, ConfigDict
from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.orchestration.routing import should_run_historian


# ===========================================================================
# EdgeType
# ===========================================================================
class EdgeType(Enum):
    """
    Types of edges in a LangGraph DAG.

    This enum is used to label edges so downstream logic can interpret routing:
    - SEQUENTIAL: always traverse from A -> B after A completes
    - CONDITIONAL: traverse to B only if some condition holds (not fully evaluated yet)
    - PARALLEL: indicates branching can happen concurrently (not implemented in executor)
    - AGGREGATION: indicates many-to-one merge (not implemented in executor)
    """

    SEQUENTIAL = "sequential"      # Standard sequential execution
    CONDITIONAL = "conditional"    # Conditional routing based on state
    PARALLEL = "parallel"          # Parallel execution branches
    AGGREGATION = "aggregation"    # Multiple inputs to single node


# ===========================================================================
# GraphEdge
# ===========================================================================
class GraphEdge(BaseModel):
    """
    Definition of an edge between graph nodes.

    Why Pydantic?
    - Validates node IDs early (length, types, etc.)
    - Allows consistent serialization for logging/debugging
    - Fits the wider OSSS ecosystem which is Pydantic-first

    NOTE about `condition`:
    - It is typed as Callable[[AgentContext], bool]
    - It is allowed as an arbitrary type (Pydantic config)
    - It is currently NOT evaluated by GraphExecutor (placeholder for future)
    """

    # ----------------------------------------------------------------------
    # Source node ID
    # ----------------------------------------------------------------------
    from_node: str = Field(
        ...,
        description="Source node identifier (must match a node key in GraphDefinition.nodes)",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "refiner_node"},
    )

    # ----------------------------------------------------------------------
    # Destination node ID
    # ----------------------------------------------------------------------
    to_node: str = Field(
        ...,
        description="Destination node identifier (must match a node key in GraphDefinition.nodes)",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "critic_node"},
    )

    # ----------------------------------------------------------------------
    # Edge routing type
    # ----------------------------------------------------------------------
    edge_type: EdgeType = Field(
        ...,
        description="Type of edge (sequential/conditional/parallel/aggregation)",
    )

    # ----------------------------------------------------------------------
    # Optional condition function (future feature)
    # ----------------------------------------------------------------------
    condition: Optional[Callable[[AgentContext], bool]] = Field(
        default=None,
        description="Optional condition function for conditional edges; not currently evaluated in executor",
    )

    # ----------------------------------------------------------------------
    # Human-readable name for the condition (useful for debugging/OpenAPI)
    # ----------------------------------------------------------------------
    condition_name: Optional[str] = Field(
        default=None,
        description="Optional name/description of the condition (debugging/observability)",
        max_length=200,
        json_schema_extra={"example": "high_confidence_check"},
    )

    # ----------------------------------------------------------------------
    # Arbitrary metadata: priorities, timeouts, origin, etc.
    # ----------------------------------------------------------------------
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional edge metadata",
        json_schema_extra={"example": {"priority": "high", "timeout_seconds": 30}},
    )

    # ----------------------------------------------------------------------
    # Pydantic config:
    # - extra='forbid': fail fast on unexpected fields
    # - validate_assignment: enforce validation when attributes are mutated
    # - arbitrary_types_allowed: required for Callable types / non-Pydantic objects
    # ----------------------------------------------------------------------
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a simple dictionary representation.

        NOTE:
        - We serialize edge_type as its `.value` (string) for readability.
        - We do NOT serialize the actual `condition` callable (non-serializable).
        """
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "edge_type": self.edge_type.value,
            "condition_name": self.condition_name,
            "metadata": self.metadata or {},
        }


# ===========================================================================
# GraphDefinition
# ===========================================================================
class GraphDefinition(BaseModel):
    """
    Complete graph definition consisting of nodes and edges.

    This is the "compiled" representation produced by GraphBuilder.

    Fields:
    - nodes: mapping of node_id -> LangGraphNodeDefinition (from each agent)
    - edges: list of GraphEdge objects describing connectivity
    - entry_points: nodes that can start execution (no incoming edges)
    - exit_points: nodes that can end execution (no outgoing edges)
    - metadata: extra descriptive/diagnostic info
    """

    # Nodes are keyed by node_id; values are agent-provided node definitions
    nodes: Dict[str, LangGraphNodeDefinition] = Field(
        ...,
        description="Dictionary mapping node IDs to their definitions",
        json_schema_extra={
            "example": {
                "refiner": {"node_type": "processor", "agent_name": "Refiner"},
                "critic": {"node_type": "processor", "agent_name": "Critic"},
            }
        },
    )

    # Edges define directed connectivity between nodes
    edges: List[GraphEdge] = Field(
        ...,
        description="List of edges defining the graph connectivity",
        json_schema_extra={
            "example": [
                {"from_node": "refiner", "to_node": "critic", "edge_type": "sequential"}
            ]
        },
    )

    # Nodes that begin the graph. Typically nodes with no incoming edges.
    entry_points: List[str] = Field(
        ...,
        description="List of node IDs that serve as graph entry points",
        min_length=1,
        json_schema_extra={"example": ["refiner"]},
    )

    # Nodes that terminate the graph. Typically nodes with no outgoing edges.
    exit_points: List[str] = Field(
        ...,
        description="List of node IDs that serve as graph exit points",
        min_length=1,
        json_schema_extra={"example": ["synthesis"]},
    )

    # Arbitrary metadata for diagnostics and UI
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional graph metadata and configuration",
        json_schema_extra={
            "example": {
                "version": "1.0",
                "description": "Standard agent processing pipeline",
                "parallel_capable": True,
            }
        },
    )

    # Pydantic config similar to GraphEdge
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,  # LangGraphNodeDefinition may contain non-Pydantic types
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert graph definition to a JSON-friendly dict.

        NOTE:
        - node definitions are converted via node_def.to_dict()
        - edges are converted via edge.to_dict()
        """
        return {
            "nodes": {node_id: node_def.to_dict() for node_id, node_def in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "entry_points": self.entry_points,
            "exit_points": self.exit_points,
            "metadata": self.metadata,
        }


# ===========================================================================
# GraphValidationError
# ===========================================================================
class GraphValidationError(Exception):
    """
    Error raised when a graph fails structural validation.

    This exception is raised by :class:`GraphBuilder` when one of the following
    conditions is detected:

    * No agents are provided.
    * Edges reference nodes that do not exist in the graph.
    * The graph contains cycles (it is not a DAG).
    * Entry or exit points are missing or invalid.
    """
    pass


# ===========================================================================
# GraphBuilder
# ===========================================================================
class GraphBuilder:
    """
    Builder for creating LangGraph-compatible graphs from OSSS agents.

    High-level flow:
    1) Agents are registered with the builder.
    2) Each agent provides a LangGraphNodeDefinition (node definition).
    3) Edges are built from:
       - agent dependency declarations
       - optional custom edges
       - optional custom routing declarations
    4) Entry/exit points are computed.
    5) Graph is validated (missing nodes, cycles, etc.)

    This does NOT create an actual LangGraph object yet.
    It produces a GraphDefinition that can be translated later.
    """

    def __init__(self) -> None:
        # Registry of agent name -> agent instance
        # NOTE: stored by lowercased agent.name to avoid case mismatches.
        self.agents: Dict[str, BaseAgent] = {}

        # Custom edges explicitly added by callers (overrides/extra wiring)
        self.custom_edges: List[GraphEdge] = []

        # Custom routing map:
        # from_node -> routing_func(context) -> next_node_name
        # NOTE: GraphExecutor does not evaluate this yet; edges are created as placeholders.
        self.custom_routing: Dict[str, Callable[[AgentContext], str]] = {}

    def build_for_query(self, query: str) -> GraphDefinition:
        graph_def = self.build()

        # If historian exists but query doesn't warrant it, remove it from nodes/edges
        if "historian" in graph_def.nodes and not should_run_historian(query):
            # Remove node
            graph_def.nodes.pop("historian", None)

            # Remove edges involving historian
            graph_def.edges = [
                e for e in graph_def.edges
                if e.from_node != "historian" and e.to_node != "historian"
            ]

            # Recompute entry/exit points after removal
            graph_def.entry_points = self._find_entry_points(graph_def.nodes, graph_def.edges)
            graph_def.exit_points = self._find_exit_points(graph_def.nodes, graph_def.edges)

            # Update metadata
            graph_def.metadata["historian_skipped"] = True

        self._validate_graph(graph_def)
        return graph_def

    def add_agent(self, agent: BaseAgent) -> "GraphBuilder":
        """
        Register a single agent.

        Implementation detail:
        - Stores the agent using `agent.name.lower()` as the key.
        - This makes subsequent node lookups consistent even if original names differ in case.

        Returns:
            Self (to enable fluent chaining)
        """
        self.agents[agent.name.lower()] = agent
        return self

    def add_agents(self, agents: List[BaseAgent]) -> "GraphBuilder":
        """
        Register multiple agents.

        This is convenience around add_agent().

        Returns:
            Self (to enable fluent chaining)
        """
        for agent in agents:
            self.add_agent(agent)
        return self

    def add_edge(self, edge: GraphEdge) -> "GraphBuilder":
        """
        Add an explicit edge.

        Use cases:
        - Override default dependency wiring
        - Force ordering even if dependencies aren't declared
        - Add conditional/parallel/aggregation semantics

        NOTE:
        - Validation still occurs in build()
        """
        self.custom_edges.append(edge)
        return self

    def add_conditional_routing(
        self,
        from_node: str,
        routing_func: Callable[[AgentContext], str],
        condition_name: str = "custom_routing",
    ) -> "GraphBuilder":
        """
        Register custom routing behavior for a node.

        Intended behavior (future):
        - After from_node executes, routing_func(context) decides which node to go next.
        - This could implement "retry", "branching", "quality gates", etc.

        Current behavior:
        - GraphBuilder will generate CONDITIONAL edges from `from_node` to all other nodes.
        - GraphExecutor will currently take *all* conditional edges (placeholder).

        Params:
            from_node: the node that branches
            routing_func: function mapping context -> next node name
            condition_name: descriptive label (not used directly yet)
        """
        self.custom_routing[from_node] = routing_func
        return self

    def build(self) -> GraphDefinition:
        """
        Build and validate a GraphDefinition.

        Steps:
        - Fail fast if no agents
        - Ask each agent for its node definition
        - Build edges (dependencies + custom edges + custom routing placeholders)
        - Determine entry and exit points
        - Validate the resulting graph (node existence, cycles, entry/exit correctness)

        Raises:
            GraphValidationError: If no agents are provided.
            GraphValidationError: If an edge references a node that does not exist.
            GraphValidationError: If the graph contains cycles.
            GraphValidationError: If entry or exit points are missing or invalid.
        """
        if not self.agents:
            raise GraphValidationError("Cannot build graph with no agents")

        # ------------------------------------------------------------------
        # 1) Convert agents into node definitions
        # ------------------------------------------------------------------
        nodes: Dict[str, LangGraphNodeDefinition] = {}

        for agent_name, agent in self.agents.items():
            # Each agent defines how it appears as a graph node
            node_def = agent.get_node_definition()
            nodes[agent_name] = node_def

        # ------------------------------------------------------------------
        # 2) Build edges from dependencies and custom user additions
        # ------------------------------------------------------------------
        edges = self._build_edges(nodes)

        # ------------------------------------------------------------------
        # 3) Compute entry/exit points based on edge directions
        # ------------------------------------------------------------------
        entry_points = self._find_entry_points(nodes, edges)
        exit_points = self._find_exit_points(nodes, edges)

        # ------------------------------------------------------------------
        # 4) Construct GraphDefinition
        # ------------------------------------------------------------------
        graph_def = GraphDefinition(
            nodes=nodes,
            edges=edges,
            entry_points=entry_points,
            exit_points=exit_points,
            metadata={
                "created_by": "OSSS GraphBuilder",
                "agent_count": len(self.agents),
                "edge_count": len(edges),
                "has_custom_routing": len(self.custom_routing) > 0,
            },
        )

        # ------------------------------------------------------------------
        # 5) Validate the graph before returning
        # ------------------------------------------------------------------
        self._validate_graph(graph_def)

        return graph_def

    def _build_edges(self, nodes: Dict[str, LangGraphNodeDefinition]) -> List[GraphEdge]:
        """
        Build graph edges from:
        1) Explicit custom edges (caller provided)
        2) Agent-declared dependencies (node_def.dependencies)
        3) Custom routing declarations (placeholder conditional edges)

        NOTE:
        - This function does not remove duplicates; duplicates may be present.
        - Validation only checks node existence and cycles, not duplicate edges.
        """
        edges: List[GraphEdge] = []

        # 1) Caller-provided edges come first so they’re included as-is
        edges.extend(self.custom_edges)

        # 2) Dependency edges:
        # If node_def.dependencies lists ["a", "b"], create edges:
        # a -> node_id, b -> node_id
        for node_id, node_def in nodes.items():
            for dependency in node_def.dependencies:
                if dependency in nodes:
                    edges.append(
                        GraphEdge(
                            from_node=dependency,
                            to_node=node_id,
                            edge_type=EdgeType.SEQUENTIAL,
                            metadata={"source": "dependency"},
                        )
                    )

        # 3) Custom routing edges:
        # Current placeholder behavior: add CONDITIONAL edges from from_node to every other node
        # Real behavior would narrow this to possible targets or evaluate routing_func.
        for from_node, routing_func in self.custom_routing.items():
            if from_node in nodes:
                for target_node in nodes.keys():
                    if target_node != from_node:
                        edges.append(
                            GraphEdge(
                                from_node=from_node,
                                to_node=target_node,
                                edge_type=EdgeType.CONDITIONAL,
                                condition_name=f"route_to_{target_node}",
                                metadata={"source": "custom_routing"},
                            )
                        )

        return edges

    def _find_entry_points(
        self,
        nodes: Dict[str, LangGraphNodeDefinition],
        edges: List[GraphEdge],
    ) -> List[str]:
        """
        Entry points are nodes with NO incoming edges.

        Algorithm:
        - Gather all `to_node` values (incoming targets)
        - Any node_id not in that set is an entry point

        Fallback:
        - If graph is fully connected in cycles/loops (or incorrect edges) and entry points are empty,
          pick the first node as a default to avoid returning an empty list.
        """
        nodes_with_incoming = {edge.to_node for edge in edges}
        entry_points = [node_id for node_id in nodes.keys() if node_id not in nodes_with_incoming]

        if not entry_points and nodes:
            entry_points = [list(nodes.keys())[0]]

        return entry_points

    def _find_exit_points(
        self,
        nodes: Dict[str, LangGraphNodeDefinition],
        edges: List[GraphEdge],
    ) -> List[str]:
        """
        Exit points are nodes with NO outgoing edges.

        Algorithm:
        - Gather all `from_node` values (outgoing sources)
        - Any node_id not in that set is an exit point

        Fallback:
        - If no exit points found, choose the last node as a default.
        """
        nodes_with_outgoing = {edge.from_node for edge in edges}
        exit_points = [node_id for node_id in nodes.keys() if node_id not in nodes_with_outgoing]

        if not exit_points and nodes:
            exit_points = [list(nodes.keys())[-1]]

        return exit_points

    def _validate_graph(self, graph_def: GraphDefinition) -> None:
        """
        Validate the structural correctness of a graph.

        Checks:
        1) Every edge endpoint exists in graph_def.nodes
        2) Graph contains no cycles (DAG requirement)
        3) entry_points is non-empty and all entry points exist
        4) exit points exist

        Raises:
            GraphValidationError with a descriptive message.
        """
        # ------------------------------------------------------------------
        # 1) Ensure all edge endpoints exist
        # ------------------------------------------------------------------
        node_ids = set(graph_def.nodes.keys())

        for edge in graph_def.edges:
            if edge.from_node not in node_ids:
                raise GraphValidationError(f"Edge from_node '{edge.from_node}' not found in nodes")
            if edge.to_node not in node_ids:
                raise GraphValidationError(f"Edge to_node '{edge.to_node}' not found in nodes")

        # ------------------------------------------------------------------
        # 2) Ensure no cycles exist
        # ------------------------------------------------------------------
        if self._has_cycles(graph_def):
            raise GraphValidationError("Graph contains cycles")

        # ------------------------------------------------------------------
        # 3) Validate entry points
        # ------------------------------------------------------------------
        if not graph_def.entry_points:
            raise GraphValidationError("Graph must have at least one entry point")

        for entry_point in graph_def.entry_points:
            if entry_point not in node_ids:
                raise GraphValidationError(f"Entry point '{entry_point}' not found in nodes")

        # ------------------------------------------------------------------
        # 4) Validate exit points
        # ------------------------------------------------------------------
        for exit_point in graph_def.exit_points:
            if exit_point not in node_ids:
                raise GraphValidationError(f"Exit point '{exit_point}' not found in nodes")

    def _has_cycles(self, graph_def: GraphDefinition) -> bool:
        """
        Detect cycles via DFS color-marking.

        Approach:
        - Build adjacency list from edges
        - Use classic DFS colors:
          WHITE: unvisited
          GRAY: visiting (in recursion stack)
          BLACK: fully processed
        - If we encounter a GRAY node, we found a back-edge => cycle.
        """
        # Build adjacency list (node -> list of outgoing neighbors)
        adjacency: Dict[str, List[str]] = {node_id: [] for node_id in graph_def.nodes.keys()}
        for edge in graph_def.edges:
            adjacency[edge.from_node].append(edge.to_node)

        WHITE, GRAY, BLACK = 0, 1, 2
        colors = {node_id: WHITE for node_id in graph_def.nodes.keys()}

        def dfs(node: str) -> bool:
            # GRAY => we hit a node still in the current recursion stack => cycle
            if colors[node] == GRAY:
                return True
            # BLACK => already fully processed, no cycle from here
            if colors[node] == BLACK:
                return False

            colors[node] = GRAY
            for neighbor in adjacency[node]:
                if dfs(neighbor):
                    return True
            colors[node] = BLACK
            return False

        # Start DFS from any unvisited node to cover disconnected graphs
        for node_id in graph_def.nodes.keys():
            if colors[node_id] == WHITE:
                if dfs(node_id):
                    return True

        return False


# ===========================================================================
# GraphExecutor
# ===========================================================================
class GraphExecutor:
    """
    Executor for running graphs built by GraphBuilder.

    This is NOT a full LangGraph runtime.
    It is a lightweight simulator used to validate that:
    - Nodes can be executed in some order
    - Edges can be traversed
    - Context can flow through node invocations

    Current limitations:
    - CONDITIONAL edges are not actually conditioned; all targets are taken.
    - PARALLEL edges are not executed concurrently.
    - AGGREGATION is not implemented.
    - Infinite-loop prevention is crude (execution_order length heuristic).
    """

    def __init__(self, graph_def: GraphDefinition, agents: Dict[str, BaseAgent]) -> None:
        # GraphDefinition describing nodes/edges/entry/exit
        self.graph_def = graph_def

        # Mapping node_id -> agent instance used for actual execution
        self.agents = agents

    async def execute(self, initial_context: AgentContext) -> AgentContext:
        """
        Execute the graph starting from entry points.

        Algorithm (high level):
        - Start from graph_def.entry_points
        - For each node:
          - invoke the corresponding agent (if present)
          - add node to visited set
          - compute next nodes via outgoing edges
        - Continue until no next nodes remain or loop guard triggers

        Returns:
            The final AgentContext after executing reachable nodes.

        Side effects:
            Adds execution trace metadata into context.execution_state:
            - graph_execution_order
            - graph_nodes_visited
        """
        current_context = initial_context

        # Track what nodes we've executed to avoid re-running
        visited_nodes: Set[str] = set()

        # Record execution order for debugging / observability
        execution_order: List[str] = []

        # Start execution from the graph entry points
        current_nodes = self.graph_def.entry_points.copy()

        while current_nodes:
            next_nodes: List[str] = []

            for node_id in current_nodes:
                # Skip nodes already executed (prevents simple cycles/revisits)
                if node_id in visited_nodes:
                    continue

                # Execute only if we have a matching agent
                # (GraphDefinition may contain nodes that are not executable here)
                if node_id in self.agents:
                    agent = self.agents[node_id]

                    # Invoke agent and update context (context is the shared state carrier)
                    current_context = await agent.invoke(current_context)

                    visited_nodes.add(node_id)
                    execution_order.append(node_id)

                    # Determine what nodes to execute next
                    next_nodes.extend(self._get_next_nodes(node_id, current_context))

            # De-dupe next nodes so we don't schedule redundant work
            current_nodes = list(set(next_nodes))

            # Loop guard: if we keep adding nodes beyond reasonable bounds, stop.
            # This protects against miswired conditional edges, cycles, or routing explosions.
            if len(execution_order) > len(self.graph_def.nodes) * 2:
                break

        # Attach execution trace to the context for debugging/telemetry
        current_context.execution_state["graph_execution_order"] = execution_order
        current_context.execution_state["graph_nodes_visited"] = list(visited_nodes)

        return current_context

    def _get_next_nodes(self, current_node: str, context: AgentContext) -> List[str]:
        """
        Determine the next nodes to run after `current_node`.

        Current behavior:
        - SEQUENTIAL: always follow the edge
        - CONDITIONAL: also follow the edge (placeholder; does not evaluate `edge.condition`)
        - Other edge types currently ignored

        In a real implementation:
        - CONDITIONAL would check edge.condition(context) (or use routing_func)
        - PARALLEL would schedule multiple nodes simultaneously
        - AGGREGATION would wait for all incoming branches
        """
        next_nodes: List[str] = []

        for edge in self.graph_def.edges:
            if edge.from_node == current_node:
                if edge.edge_type == EdgeType.SEQUENTIAL:
                    next_nodes.append(edge.to_node)

                elif edge.edge_type == EdgeType.CONDITIONAL:
                    # Placeholder behavior:
                    # - Always include conditional targets.
                    # - Real implementation would evaluate edge.condition(context) or routing function.
                    next_nodes.append(edge.to_node)

        return next_nodes
