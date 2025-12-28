"""
Prototype DAG implementation for OSSS LangGraph integration.

This module demonstrates how OSSS's historical *sequential* agent execution
can be represented as a LangGraph-compatible directed acyclic graph (DAG).

Key purpose of this file:
- Proof-of-concept (POC) executor for a tiny graph: Refiner → Critic
- Demonstrate:
  - converting agents into node adapters
  - building a graph definition with edges + conditional routing
  - executing nodes in a graph-like traversal loop
  - collecting rich execution metadata (timings, edges, errors)

Graph patterns (kept in sync with orchestration layer):
- "standard":    informational pattern (refiner → final in production; here we demo refiner → critic)
- "data_query":  action/DB pattern (refiner → data_query in production; not fully modeled in this POC)

This is NOT a full LangGraph engine; it is a simplified educational scaffold.
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import asyncio                    # Async execution support (await node runs, sleep, etc.)
import time                       # Timing measurements for performance metrics
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass # Lightweight container for execution results

# ---------------------------------------------------------------------------
# OSSS / OSSS imports
# ---------------------------------------------------------------------------

from OSSS.ai.context import AgentContext           # Shared context passed between agents
from OSSS.ai.agents.registry import get_agent_registry  # Factory/registry for agent instantiation

# OpenAI LLM configuration and concrete LLM implementation
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM

# Observability (structured logger)
from OSSS.ai.observability import get_logger

# ---------------------------------------------------------------------------
# Local LangGraph integration scaffolding
# ---------------------------------------------------------------------------
# These adapters are the bridge layer between:
# - OSSS agents (BaseAgent-ish) and
# - a graph execution model (LangGraph nodes)
#
# They typically normalize:
# - how agents are executed
# - how inputs/outputs are validated
# - how routing decisions are made
from .adapter import (
    LangGraphNodeAdapter,         # Base adapter interface type
    StandardNodeAdapter,          # "Normal" node wrapper around a standard agent
    ConditionalNodeAdapter,       # Node wrapper supporting routing functions
    ExecutionNodeConfiguration,   # Per-node run configuration (timeouts, retries, step_id)
)

# Graph builder and graph definition types
from .graph_builder import GraphBuilder, GraphEdge, EdgeType, GraphDefinition

# Module-level logger
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pattern constants (kept aligned with orchestration)
# ---------------------------------------------------------------------------

STANDARD_PATTERN = "standard"
DATA_QUERY_PATTERN = "data_query"
SUPPORTED_GRAPH_PATTERNS = {STANDARD_PATTERN, DATA_QUERY_PATTERN}


# ---------------------------------------------------------------------------
# Execution Result Model
# ---------------------------------------------------------------------------

@dataclass
class DAGExecutionResult:
    """
    Result of DAG execution with comprehensive metadata.

    This is intentionally verbose to support:
    - debugging "why did this workflow do that?"
    - validating that the graph traversal matches expectations
    - performance analysis (per-node timings, overhead, etc.)
    """

    # The final AgentContext after graph execution completes (successful or not).
    final_context: AgentContext

    # Overall success flag (typically: no errors and expected nodes executed).
    success: bool

    # Total end-to-end execution time in milliseconds (computed at the top level).
    total_execution_time_ms: float

    # Ordered list of node IDs executed (e.g., ["refiner", "critic"]).
    nodes_executed: List[str]

    # Edges traversed in order (e.g., [("refiner", "critic")]).
    edges_traversed: List[Tuple[str, str]]

    # List of exceptions encountered during execution (can be empty on success).
    errors: List[Exception]

    # Detailed per-step execution record (node_id, timing, output lengths, errors).
    execution_path: List[Dict[str, Any]]

    # Aggregated performance metrics (totals, averages, overhead).
    performance_metrics: Dict[str, Any]


class PrototypeDAGExecutor:
    """
    Prototype DAG executor demonstrating LangGraph integration.

    This class models (in a simplified way) how LangGraph-style execution works:
    - Start from entry nodes
    - Execute nodes
    - Use edges + conditional routing to determine next nodes
    - Stop when no more nodes remain or on failure/limits

    Important limitations (as written):
    - Not a full scheduler
    - Only basic conditional routing support
    - No true parallelism (flag exists but not implemented here)
    - No topological sorting; instead uses a simple traversal loop

    Pattern semantics in this prototype:
    - graph_pattern = "standard":
        Demonstrates an informational flow by running refiner → critic.
        (Production "standard" is refiner → final; critic here is a stand-in.)
    - graph_pattern = "data_query":
        Accepted and logged for parity with orchestration, but currently runs
        the same refiner → critic demo flow.
    """

    def __init__(
        self,
        enable_parallel_execution: bool = False,
        max_execution_time_seconds: float = 300.0,
    ) -> None:
        """
        Initialize the prototype DAG executor.

        Parameters
        ----------
        enable_parallel_execution : bool
            If True, executor *intends* to support parallel execution of independent nodes.
            NOTE: This prototype does not actually schedule parallel tasks yet; the flag is here
            to show how the design could expand.
        max_execution_time_seconds : float
            Maximum allowed end-to-end time for a DAG run. (Currently not enforced in traversal.)
        """
        self.enable_parallel_execution = enable_parallel_execution
        self.max_execution_time_seconds = max_execution_time_seconds

        # Dedicated logger for this executor class (keeps logs distinguishable)
        self.logger = get_logger(f"{__name__}.PrototypeDAGExecutor")

        # Simple execution counters used for high-level health/metrics reporting
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0

    async def execute_refiner_critic_dag(
        self,
        query: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> DAGExecutionResult:
        """
        Execute the prototype Refiner → Critic DAG.

        This is the "main demo" entrypoint for the POC. It honors the same
        graph_pattern contract as the real orchestrator, but is deliberately
        limited to the two canonical patterns:

        - "standard":    informational pattern (this POC)
        - "data_query":  action/DB pattern (accepted, but currently mapped to
                         the same POC flow for demonstration purposes).

        Parameters
        ----------
        query : str
            Input query string.
        config : Dict[str, Any], optional
            Execution configuration controlling validation, retries, timeouts, etc.
            May include:
              - graph_pattern: "standard" or "data_query" (default: "standard")

        Returns
        -------
        DAGExecutionResult
            Comprehensive execution result including path and metrics.
        """
        start_time = time.time()

        # Ensure config is a dictionary to simplify downstream access
        config = config or {}

        # Normalize graph_pattern to one of the two supported patterns
        graph_pattern = str(config.get("graph_pattern") or STANDARD_PATTERN).strip()
        if graph_pattern not in SUPPORTED_GRAPH_PATTERNS:
            self.logger.warning(
                f"Unsupported graph_pattern '{graph_pattern}' for prototype "
                f"DAG; defaulting to '{STANDARD_PATTERN}'"
            )
            graph_pattern = STANDARD_PATTERN
        config["graph_pattern"] = graph_pattern

        self.logger.info(
            "Starting prototype DAG execution",
            extra={
                "graph_pattern": graph_pattern,
                "query_preview": query[:100],
            },
        )
        self.total_executions += 1

        try:
            # ----------------------------------------------------------------
            # Initialize core execution components
            # ----------------------------------------------------------------

            # Create a new AgentContext to carry query, outputs, and state
            context = AgentContext(query=query)

            # Registry is responsible for creating agent instances by name
            registry = get_agent_registry()

            # LLM initialization (OpenAI-based) used for agent construction
            llm = self._initialize_llm()

            # ----------------------------------------------------------------
            # Construct the actual agent instances
            # ----------------------------------------------------------------
            # These are OSSS agents that will be wrapped in adapters
            refiner_agent = registry.create_agent("refiner", llm=llm)
            critic_agent = registry.create_agent("critic", llm=llm)

            # ----------------------------------------------------------------
            # Wrap agents into node adapters
            # ----------------------------------------------------------------
            # StandardNodeAdapter:
            # - runs the agent
            # - optionally validates state/output
            # - returns a normalized result envelope
            refiner_node = StandardNodeAdapter(
                agent=refiner_agent,
                node_id="refiner",
                enable_state_validation=config.get("enable_validation", True),
            )

            # The prototype also sketches a routing function after refiner,
            # but note: it is defined here and not directly wired into critic_node.
            # The actual routing in this prototype is set up in _build_refiner_critic_graph().
            def route_after_refiner(context: AgentContext) -> List[str]:
                """Route to critic if refiner succeeded, end if failed."""
                refiner_final = context.get_output("Refiner")
                if refiner_final and len(str(refiner_final).strip()) > 0:
                    return ["critic"]
                else:
                    return ["end"]

            # ConditionalNodeAdapter:
            # - behaves like a standard node wrapper
            # - adds a routing function used to select next nodes
            #
            # Here, it always routes to "end" after critic runs.
            critic_node = ConditionalNodeAdapter(
                agent=critic_agent,
                routing_function=lambda ctx: ["end"],  # Always end after critic
                node_id="critic",
            )

            # ----------------------------------------------------------------
            # Build the graph definition (nodes + edges + conditional routing)
            # ----------------------------------------------------------------
            graph_def = self._build_refiner_critic_graph(refiner_node, critic_node)

            # ----------------------------------------------------------------
            # Execute the graph traversal
            # ----------------------------------------------------------------
            execution_result = await self._execute_dag(
                graph_def=graph_def,
                initial_context=context,
                node_adapters={"refiner": refiner_node, "critic": critic_node},
                config=config,
            )

            # Compute total end-to-end time in milliseconds
            total_time_ms = (time.time() - start_time) * 1000

            # Define what "success" means for this POC:
            # - no errors were recorded
            # - at least one node executed (refiner should always run)
            success = (
                len(execution_result.errors) == 0
                and len(execution_result.nodes_executed) >= 1
            )

            # Update counters for external reporting
            if success:
                self.successful_executions += 1
            else:
                self.failed_executions += 1

            # Build the final result with computed metrics
            result = DAGExecutionResult(
                final_context=execution_result.final_context,
                success=success,
                total_execution_time_ms=total_time_ms,
                nodes_executed=execution_result.nodes_executed,
                edges_traversed=execution_result.edges_traversed,
                errors=execution_result.errors,
                execution_path=execution_result.execution_path,
                performance_metrics=self._calculate_performance_metrics(
                    execution_result, total_time_ms, graph_pattern
                ),
            )

            self.logger.info(
                "DAG execution completed",
                extra={
                    "success": success,
                    "time_ms": total_time_ms,
                    "nodes": len(execution_result.nodes_executed),
                    "graph_pattern": graph_pattern,
                },
            )

            return result

        except Exception as e:
            # Any unhandled exception here means the DAG run failed at a top-level
            self.failed_executions += 1
            total_time_ms = (time.time() - start_time) * 1000

            self.logger.error(
                f"DAG execution failed after {total_time_ms:.2f}ms: {e}",
                extra={"graph_pattern": config.get("graph_pattern", STANDARD_PATTERN)},
            )

            # Return a structured failure result so callers can still inspect metrics
            return DAGExecutionResult(
                final_context=AgentContext(query=query),
                success=False,
                total_execution_time_ms=total_time_ms,
                nodes_executed=[],
                edges_traversed=[],
                errors=[e],
                execution_path=[],
                performance_metrics={
                    "error": str(e),
                    "execution_time_ms": total_time_ms,
                    "graph_pattern": config.get("graph_pattern", STANDARD_PATTERN),
                },
            )

    def _build_refiner_critic_graph(
        self,
        refiner_node: StandardNodeAdapter,
        critic_node: ConditionalNodeAdapter,
    ) -> GraphDefinition:
        """
        Build a GraphDefinition for the Refiner → Critic flow.

        This method uses GraphBuilder to:
        - register nodes/agents
        - define an edge from refiner → critic
        - define conditional routing for refiner that chooses critic vs END

        Returns
        -------
        GraphDefinition
            Static representation of the graph (nodes + edges + routing).
        """
        builder = GraphBuilder()

        # Register the underlying agents. The builder typically extracts:
        # - node metadata
        # - schemas
        # - dependencies
        builder.add_agent(refiner_node.agent)
        builder.add_agent(critic_node.agent)

        # Define the edge from refiner to critic as CONDITIONAL
        # Even though the edge has to_node="critic", routing may still decide
        # to terminate instead.
        refiner_to_critic_edge = GraphEdge(
            from_node="refiner",
            to_node="critic",
            edge_type=EdgeType.CONDITIONAL,
            condition_name="refiner_success",
            metadata={
                "description": "Execute critic if refiner succeeds",
                "condition": "refiner_final_exists",
            },
        )
        builder.add_edge(refiner_to_critic_edge)

        # Routing function attached to the refiner node:
        # - If refiner produced output, continue to critic
        # - Otherwise terminate
        def route_from_refiner(context: AgentContext) -> str:
            """Route to critic if refiner succeeded."""
            refiner_final = context.get_output("Refiner")
            if refiner_final and len(str(refiner_final).strip()) > 0:
                return "critic"
            return "END"

        builder.add_conditional_routing(
            from_node="refiner",
            routing_func=route_from_refiner,
            condition_name="refiner_success_routing",
        )

        # Finalize and return the built graph definition
        return builder.build()

    async def _execute_dag(
        self,
        graph_def: GraphDefinition,
        initial_context: AgentContext,
        node_adapters: Dict[str, LangGraphNodeAdapter],
        config: Dict[str, Any],
    ) -> DAGExecutionResult:
        """
        Execute the DAG with the given configuration.

        This is the heart of the prototype executor:
        - Maintains a queue of "current nodes" to run
        - Executes nodes once (visited_nodes prevents re-run)
        - Uses _get_next_nodes() to determine traversal
        - Captures execution_path and errors

        NOTE:
        - max_execution_time_seconds is not enforced here (could be added).
        - enable_parallel_execution is not implemented; loop runs sequentially.
        - graph_pattern is accepted in config (standard/data_query) for parity
          with orchestration, but does not change traversal in this POC.
        """
        current_context = initial_context
        nodes_executed: List[str] = []
        edges_traversed: List[Tuple[str, str]] = []
        errors: List[Exception] = []
        execution_path: List[Dict[str, Any]] = []

        # Seed traversal using entry points from graph definition
        current_nodes = graph_def.entry_points.copy()

        # Track which nodes have already been executed to avoid repetition
        visited_nodes = set()

        # A safety brake: prevents infinite loops if routing cycles exist
        max_iterations = len(graph_def.nodes) * 2
        iteration = 0

        while current_nodes and iteration < max_iterations:
            iteration += 1
            next_nodes: List[str] = []

            for node_id in current_nodes:
                # Skip nodes already executed (prototype assumes DAG-ish behavior)
                if node_id in visited_nodes:
                    continue

                # If adapter missing, node cannot run; warn and skip
                if node_id not in node_adapters:
                    self.logger.warning(f"No adapter found for node: {node_id}")
                    continue

                self.logger.debug(f"Executing node: {node_id}")

                try:
                    node_adapter = node_adapters[node_id]

                    # Build per-node execution configuration.
                    # step_id helps trace/identify node executions in logs/telemetry.
                    node_config = ExecutionNodeConfiguration(
                        timeout_seconds=config.get("node_timeout_seconds"),
                        retry_enabled=config.get("retry_enabled", True),
                        step_id=f"{node_id}_{iteration}",
                        custom_config=config.get("node_configs", {}).get(node_id, {}),
                    )

                    # Measure node-level execution time
                    execution_start = time.time()
                    result = await node_adapter.execute(current_context, node_config)
                    execution_time_ms = (time.time() - execution_start) * 1000

                    if result.success:
                        # Update context to the node's returned context
                        current_context = result.context

                        # Mark node as executed
                        nodes_executed.append(node_id)
                        visited_nodes.add(node_id)

                        # Record detailed info about this step
                        execution_path.append(
                            {
                                "node_id": node_id,
                                "success": True,
                                "execution_time_ms": execution_time_ms,
                                "iteration": iteration,
                                # Output length is a quick proxy for "something happened"
                                "output_length": len(
                                    str(current_context.get_output(node_adapter.agent.name) or "")
                                ),
                            }
                        )

                        # Determine which nodes to execute next based on:
                        # - explicit edges
                        # - routing functions
                        node_next_nodes = self._get_next_nodes(
                            node_id, current_context, graph_def, node_adapters
                        )
                        next_nodes.extend(node_next_nodes)

                        # Record traversal edges for traceability
                        for next_node in node_next_nodes:
                            edges_traversed.append((node_id, next_node))

                        self.logger.debug(
                            f"Node {node_id} completed successfully, next nodes: {node_next_nodes}"
                        )

                    else:
                        # Node execution failed (adapter indicated failure)
                        if result.error:
                            errors.append(result.error)

                        execution_path.append(
                            {
                                "node_id": node_id,
                                "success": False,
                                "execution_time_ms": execution_time_ms,
                                "iteration": iteration,
                                "error": str(result.error) if result.error else "Unknown error",
                            }
                        )

                        self.logger.error(
                            f"Node {node_id} execution failed: {result.error}"
                        )

                        # Fail-fast: stop the DAG as soon as a node fails
                        if config.get("fail_fast", True):
                            break

                except Exception as e:
                    # Unexpected exception while executing node (adapter/agent bug, etc.)
                    errors.append(e)
                    execution_path.append(
                        {
                            "node_id": node_id,
                            "success": False,
                            "iteration": iteration,
                            "error": str(e),
                        }
                    )

                    self.logger.error(f"Unexpected error executing node {node_id}: {e}")

                    if config.get("fail_fast", True):
                        break

            # De-duplicate next nodes to avoid repeated scheduling
            current_nodes = list(set(next_nodes))

            # If nothing left to run, we have reached a terminal condition
            if not current_nodes:
                self.logger.debug("No more nodes to execute - DAG complete")
                break

            # Safety check against runaway execution
            if iteration >= max_iterations:
                self.logger.warning(f"Maximum iterations ({max_iterations}) reached")
                break

        # Return an intermediate DAGExecutionResult; caller fills in total_time_ms and metrics.
        return DAGExecutionResult(
            final_context=current_context,
            success=len(errors) == 0,
            total_execution_time_ms=0,      # computed by outer method
            nodes_executed=nodes_executed,
            edges_traversed=edges_traversed,
            errors=errors,
            execution_path=execution_path,
            performance_metrics={},         # computed by outer method
        )

    def _get_next_nodes(
        self,
        current_node: str,
        context: AgentContext,
        graph_def: GraphDefinition,
        node_adapters: Dict[str, LangGraphNodeAdapter],
    ) -> List[str]:
        """
        Determine next nodes to execute after current_node.

        Logic sources:
        1) Graph edges: SEQUENTIAL and CONDITIONAL edges add candidate nodes.
        2) Adapter routing_function (if present): adds routed nodes.

        Filtering:
        - Remove terminal markers ("END", "end", "ERROR", "error")
        - Ensure node exists in graph_def.nodes
        - De-duplicate results
        """
        next_nodes: List[str] = []

        # 1) Follow explicit edges from current node
        for edge in graph_def.edges:
            if edge.from_node == current_node:
                if edge.edge_type == EdgeType.SEQUENTIAL:
                    next_nodes.append(edge.to_node)
                elif edge.edge_type == EdgeType.CONDITIONAL:
                    # Prototype behavior: add target; routing will decide actual path
                    next_nodes.append(edge.to_node)

        # 2) Apply adapter routing if available (conditional adapters)
        if current_node in node_adapters:
            adapter = node_adapters[current_node]
            if hasattr(adapter, "routing_function"):
                try:
                    routed_nodes = adapter.routing_function(context)
                    next_nodes.extend(routed_nodes)
                except Exception as e:
                    self.logger.error(f"Routing function failed for {current_node}: {e}")

        # Filter out invalid or terminal nodes
        valid_next_nodes: List[str] = []
        for node in next_nodes:
            if node in ["END", "end", "ERROR", "error"]:
                continue
            if node in graph_def.nodes:
                valid_next_nodes.append(node)

        # De-duplicate before returning
        return list(set(valid_next_nodes))

    def _initialize_llm(self) -> OpenAIChatLLM:
        """
        Initialize the LLM used for agent creation.

        In this prototype:
        - LLM is OpenAIChatLLM configured from OpenAIConfig.
        - This matches how production/CLI often constructs an LLM.

        Returns
        -------
        OpenAIChatLLM
            Configured LLM instance.
        """
        llm_config = OpenAIConfig.load()
        return OpenAIChatLLM(
            api_key=llm_config.api_key,
            model=llm_config.model,
            base_url=llm_config.base_url,
        )

    def _calculate_performance_metrics(
        self,
        execution_result: DAGExecutionResult,
        total_time_ms: float,
        graph_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.

        Metrics include:
        - total wall-clock time
        - summed node execution time (from execution_path)
        - overhead time (wall-clock minus node time)
        - counts of nodes/edges/errors
        - average node time
        - rough efficiency ratio
        - graph_pattern used for the run (standard/data_query)
        """
        nodes_count = len(execution_result.nodes_executed)
        edges_count = len(execution_result.edges_traversed)

        # Extract per-node execution time from recorded path
        node_timings: Dict[str, float] = {}
        total_node_time = 0.0

        for step in execution_result.execution_path:
            if step.get("success", False):
                node_id = step["node_id"]
                exec_time = step.get("execution_time_ms", 0)
                node_timings[node_id] = exec_time
                total_node_time += exec_time

        normalized_pattern = (
            graph_pattern if graph_pattern in SUPPORTED_GRAPH_PATTERNS else STANDARD_PATTERN
        )

        return {
            "total_execution_time_ms": total_time_ms,
            "total_node_execution_time_ms": total_node_time,
            "overhead_time_ms": total_time_ms - total_node_time,
            "nodes_executed": nodes_count,
            "edges_traversed": edges_count,
            "errors_count": len(execution_result.errors),
            "success_rate": 1.0 if len(execution_result.errors) == 0 else 0.0,
            "average_node_time_ms": (total_node_time / nodes_count if nodes_count > 0 else 0),
            "node_timings": node_timings,
            "execution_efficiency": (total_node_time / total_time_ms if total_time_ms > 0 else 0),
            "graph_pattern": normalized_pattern,
        }

    def get_executor_statistics(self) -> Dict[str, Any]:
        """
        Get executor-level statistics across all runs.

        This supports:
        - health endpoints
        - quick diagnosis of frequent failures
        - verifying improvements over time

        Returns:
            dict including total runs, success rate, and configuration.
        """
        success_rate = (
            self.successful_executions / self.total_executions
            if self.total_executions > 0
            else 0
        )

        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "configuration": {
                "enable_parallel_execution": self.enable_parallel_execution,
                "max_execution_time_seconds": self.max_execution_time_seconds,
                "supported_graph_patterns": sorted(SUPPORTED_GRAPH_PATTERNS),
            },
        }


async def run_prototype_demo(
    query: str = "Analyze the benefits of renewable energy",
) -> DAGExecutionResult:
    """
    Run a demonstration of the prototype DAG execution.

    This is a convenience wrapper that:
    - creates a PrototypeDAGExecutor
    - defines a reasonable default config
    - executes the Refiner → Critic DAG using the "standard" pattern
    - logs a brief summary of results

    Parameters
    ----------
    query : str
        Query to process through the DAG.

    Returns
    -------
    DAGExecutionResult
        Complete execution result including performance metrics.
    """
    executor = PrototypeDAGExecutor(
        enable_parallel_execution=False,  # Start sequential to keep behavior deterministic
        max_execution_time_seconds=120.0,
    )

    # Demo config with safe defaults
    config = {
        "enable_validation": True,
        "fail_fast": True,
        "retry_enabled": True,
        "node_timeout_seconds": 30.0,
        # Explicitly demonstrate the "standard" graph pattern
        "graph_pattern": STANDARD_PATTERN,
    }

    result = await executor.execute_refiner_critic_dag(query, config)

    # Log a concise summary for demo output
    logger.info("Demo execution completed:")
    logger.info(f"  Success: {result.success}")
    logger.info(f"  Execution time: {result.total_execution_time_ms:.2f}ms")
    logger.info(f"  Nodes executed: {result.nodes_executed}")
    logger.info(f"  Edges traversed: {result.edges_traversed}")
    logger.info(f"  Errors: {len(result.errors)}")
    logger.info(f"  Graph pattern: {result.performance_metrics.get('graph_pattern')}")

    return result


if __name__ == "__main__":
    # If this module is executed directly, run the demo.
    # Keeping it inline makes it easy to test manually without wiring up other tooling.
    import asyncio

    async def main() -> None:
        result = await run_prototype_demo()
        print(f"Demo result: {result.success}")
        print(f"Performance: {result.performance_metrics}")

    asyncio.run(main())
