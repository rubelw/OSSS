"""
Production LangGraph orchestrator for OSSS agents.

This module provides LangGraph integration implementing production-ready
DAG execution with StateGraph orchestration.

Features:
- True DAG-based execution using LangGraph StateGraph
- Parallel execution where dependencies allow
- Type-safe state management with TypedDict schemas
- Circuit breaker patterns for error handling
- Comprehensive logging and metrics
- State bridge integration for AgentContext compatibility
"""

import time
import uuid
from typing import Dict, Any, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.registry import get_agent_registry
from OSSS.ai.observability import get_logger
from OSSS.ai.correlation import (
    ensure_correlation_context,
    create_child_span,
    add_trace_metadata,
    CorrelationContext,
    context_correlation_id,
    context_workflow_id,
    context_trace_metadata,
)
from OSSS.ai.events import (
    emit_workflow_completed,
    emit_routing_decision_from_object,
)
from OSSS.ai.orchestration.state_bridge import AgentContextStateBridge
from OSSS.ai.orchestration.state_schemas import (
    OSSSState,
    OSSSContext,
    RefinerState,
    CriticState,
    HistorianState,
    SynthesisState,
    create_initial_state,
    validate_state_integrity,
)
from OSSS.ai.orchestration.node_wrappers import (
    NodeExecutionError,
    get_node_dependencies,
)
from OSSS.ai.orchestration.memory_manager import (
    OSSSMemoryManager,
    create_memory_manager,
)
from OSSS.ai.langgraph_backend import (
    GraphFactory,
    GraphConfig,
    GraphBuildError,
    CacheConfig,
)
from OSSS.ai.langgraph_backend.graph_patterns.conditional import (
    EnhancedConditionalPattern,
    ContextAnalyzer,
    PerformanceTracker,
)
from OSSS.ai.routing import (
    ResourceOptimizer,
    ResourceConstraints,
    OptimizationStrategy,
    RoutingDecision,
)
from OSSS.ai.rag.jsonl_rag import rag_prefetch_jsonl


logger = get_logger(__name__)


def _ensure_effective_queries(state: Dict[str, Any], base_query: str) -> None:
    """
    Ensure execution_state.effective_queries exists for the run.

    Node wrappers will overwrite per-agent values right before each agent runs:
      execution_state["effective_queries"][agent_name] = effective_query
    """
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        state["execution_state"] = {}
        exec_state = state["execution_state"]

    effective = exec_state.setdefault("effective_queries", {})
    if not isinstance(effective, dict):
        exec_state["effective_queries"] = {}
        effective = exec_state["effective_queries"]

    # Seed the baseline query for reference (node wrappers can override)
    effective.setdefault("user", base_query)


class LangGraphOrchestrator:
    """
    Production LangGraph orchestrator for OSSS agents.

    This orchestrator uses LangGraph library to provide production-ready
    DAG-based execution with advanced state management, parallel processing, and
    conditional routing capabilities.

    Features:
    - StateGraph-based DAG execution with proper dependencies
    - Parallel execution of independent agents (Refiner → [Critic, Historian] → Synthesis)
    - Type-safe state management with comprehensive validation
    - Circuit breaker patterns for robust error handling
    - Optional memory checkpointing for stateful conversations
    - Comprehensive logging and performance metrics
    """

    def __init__(
        self,
        agents_to_run: Optional[List[str]] = None,
        enable_checkpoints: bool = False,
        thread_id: Optional[str] = None,
        memory_manager: Optional[OSSSMemoryManager] = None,
        use_enhanced_routing: bool = True,
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> None:
        """
        Initialize the production LangGraph orchestrator.
        """
        # Default agents - will be optimized by enhanced routing if enabled
        self.default_agents = [
            "guard",
            # "refiner",
            # "critic",
            # "historian",
            # "synthesis",
        ]

        # Enhanced routing configuration
        self.use_enhanced_routing = use_enhanced_routing
        self.optimization_strategy = optimization_strategy

        # Initialize routing systems
        self.conditional_pattern: Optional[EnhancedConditionalPattern] = (
            EnhancedConditionalPattern() if self.use_enhanced_routing else None
        )
        self.resource_optimizer: Optional[ResourceOptimizer] = (
            ResourceOptimizer() if self.use_enhanced_routing else None
        )
        self.context_analyzer: Optional[ContextAnalyzer] = (
            ContextAnalyzer() if self.use_enhanced_routing else None
        )
        self.performance_tracker: Optional[PerformanceTracker] = (
            PerformanceTracker() if self.use_enhanced_routing else None
        )

        # Set initial agents (may be overridden by routing)
        self.agents_to_run = agents_to_run or self.default_agents
        self.enable_checkpoints = enable_checkpoints
        self.thread_id = thread_id
        self.registry = get_agent_registry()
        self.logger = get_logger(f"{__name__}.LangGraphOrchestrator")

        # Initialize memory manager
        if memory_manager:
            self.memory_manager = memory_manager
        else:
            self.memory_manager = create_memory_manager(
                enable_checkpoints=enable_checkpoints,
                thread_id=thread_id,
            )

        # Add agents property for compatibility with health checks and dry runs
        self.agents: List[BaseAgent] = []

        # Performance tracking
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0

        # State bridge for AgentContext <-> LangGraph state conversion
        self.state_bridge = AgentContextStateBridge()

        # Initialize GraphFactory for graph building
        cache_config = CacheConfig(max_size=10, ttl_seconds=1800)  # 30 minutes TTL
        self.graph_factory = GraphFactory(cache_config)

        # LangGraph components (initialized lazily)
        self._graph = None
        self._compiled_graph = None

        # Remember last run config (for graph build policy knobs)
        self._last_config: Dict[str, Any] = {}

        self.logger.info(
            f"Initialized LangGraphOrchestrator with agents: {self.agents_to_run}, "
            f"checkpoints: {self.enable_checkpoints}, thread_id: {self.thread_id}"
        )

    async def _run_guard_and_maybe_halt(
        self,
        *,
        query: str,
        config: Dict[str, Any],
        execution_id: str,
        correlation_id: str,
        orchestrator_span: Any,
        start_time: float,
        correlation_ctx: CorrelationContext,
    ) -> Optional[AgentContext]:
        """
        Run guard outside the graph. If guard sets execution_state.routing.halt,
        return an AgentContext immediately (no LangGraph execution).
        """
        # Optional toggle
        if config.get("skip_guard", False):
            return None

        guard_agent: Optional[BaseAgent] = None

        # Try a few likely registry APIs without breaking prod
        try:
            if hasattr(self.registry, "create_agent"):
                guard_agent = self.registry.create_agent("guard")
            elif hasattr(self.registry, "create"):
                guard_agent = self.registry.create("guard")
            elif hasattr(self.registry, "get"):
                maybe = self.registry.get("guard")
                guard_agent = maybe() if callable(maybe) else maybe
        except Exception:
            guard_agent = None

        if guard_agent is None:
            self.logger.warning(
                "[orchestrator] Guard agent not available; continuing without pre-guard short-circuit."
            )
            return None

        guard_ctx = AgentContext(query=query)
        guard_ctx = await guard_agent.run(guard_ctx)

        routing = (
            guard_ctx.execution_state.get("routing", {})
            if isinstance(guard_ctx.execution_state, dict)
            else {}
        )
        if routing.get("halt"):
            total_time_ms = (time.time() - start_time) * 1000
            guard_ctx.execution_state.update(
                {
                    "orchestrator_type": "langgraph-real",
                    "phase": "phase2_1",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "orchestrator_span": orchestrator_span,
                    "agents_requested": self.agents_to_run,
                    "config": config,
                    "execution_time_ms": total_time_ms,
                    "langgraph_execution": False,
                    "halted_pre_graph": True,
                    "correlation_context": correlation_ctx.to_dict(),
                }
            )
            return guard_ctx

        return None

    async def run(self, query: str, config: Optional[Dict[str, Any]] = None) -> AgentContext:
        """
        Execute agents using LangGraph StateGraph orchestration.

        Best practice (orchestrator-api refactor):
        - The orchestrator decides the execution plan (agent set + routing metadata).
        - The graph executes that plan (no extra ad-hoc routing heuristics here).
        - Nodes consume routing/profile hints via execution_state.agent_output_meta.
        """
        config = config or {}
        self._last_config = dict(config)
        start_time = time.time()

        # ------------------------------------------------------------
        # Parse (but don't apply yet): honor caller-requested agent list.
        # Guard must run first regardless.
        # ------------------------------------------------------------
        requested_agents = config.get("agents")
        if isinstance(requested_agents, list):
            requested_agents = [a for a in requested_agents if isinstance(a, str) and a.strip()]
        else:
            requested_agents = None

        routing_decision = None

        # Handle correlation context - use provided correlation_id/workflow_id if available
        provided_correlation_id = config.get("correlation_id") if config else None
        provided_workflow_id = config.get("workflow_id") if config else None

        if provided_correlation_id:
            workflow_id = provided_workflow_id or str(uuid.uuid4())
            context_correlation_id.set(provided_correlation_id)
            context_workflow_id.set(workflow_id)
            context_trace_metadata.set({})
            correlation_ctx = CorrelationContext(
                correlation_id=provided_correlation_id,
                workflow_id=workflow_id,
                metadata={},
            )
        else:
            correlation_ctx = ensure_correlation_context()

        execution_id = correlation_ctx.workflow_id
        correlation_id = correlation_ctx.correlation_id

        orchestrator_span = create_child_span("langgraph_orchestrator")

        add_trace_metadata("orchestrator_type", "langgraph-real")
        add_trace_metadata("query_length", len(query))
        add_trace_metadata("config", config)

        self.total_executions += 1

        # ------------------------------------------------------------
        # Pre-guard short-circuit: run guard ALWAYS.
        # ------------------------------------------------------------
        halted_ctx = await self._run_guard_and_maybe_halt(
            query=query,
            config=config,
            execution_id=execution_id,
            correlation_id=correlation_id,
            orchestrator_span=orchestrator_span,
            start_time=start_time,
            correlation_ctx=correlation_ctx,
        )
        if halted_ctx is not None:
            self.logger.info(
                "[orchestrator] Halted pre-graph by guard: %s",
                halted_ctx.execution_state.get("routing", {}).get("halt_reason"),
            )
            self.successful_executions += 1
            return halted_ctx

        # ------------------------------------------------------------
        # Now honor caller-requested agent list for the DAG.
        # (Guard already ran above, so callers cannot bypass safety.)
        # ------------------------------------------------------------
        if requested_agents:
            self.agents_to_run = requested_agents
            try:
                self.default_agents = requested_agents
            except Exception:
                pass

            # Graph is typically compiled/cached by topology; force rebuild when agent set changes
            self._compiled_graph = None
            self._graph = None

        # ------------------------------------------------------------
        # Enhanced routing (ONLY if caller did not request agents)
        # ------------------------------------------------------------
        if self.use_enhanced_routing and not requested_agents:
            routing_decision = await self._make_routing_decision(query, self.default_agents, config)
            self.agents_to_run = routing_decision.selected_agents

            # Agent set changed -> force rebuild
            self._compiled_graph = None
            self._graph = None

        # ------------------------------------------------------------
        # Emit routing decision event only if we actually made one
        # ------------------------------------------------------------
        if routing_decision is not None:
            emit_routing_decision_from_object(
                routing_decision,
                workflow_id=execution_id,
                correlation_id=correlation_id,
                metadata={
                    "orchestrator_type": "langgraph-real",
                    "optimization_strategy": self.optimization_strategy.value,
                    "routing_enabled": True,
                },
            )

        # Record accurate final plan in traces
        add_trace_metadata("agents_requested", list(self.agents_to_run or []))

        # ------------------------------------------------------------
        # Log final “agents to run”
        # ------------------------------------------------------------
        self.logger.info(
            f"Starting LangGraph execution for query: {query[:100]}... "
            f"(execution_id: {execution_id}, correlation_id: {correlation_id})"
        )
        self.logger.info("Execution mode: langgraph")
        self.logger.info(f"Agents to run: {self.agents_to_run}")
        if routing_decision:
            self.logger.info(f"Routing strategy: {routing_decision.routing_strategy}")
            self.logger.info(f"Routing confidence: {routing_decision.confidence_score:.2f}")
        self.logger.info(f"Config: {config}")
        self.logger.info(f"Correlation context: {correlation_ctx.to_dict()}")

        try:
            # Get or generate thread ID for this execution
            thread_id = self.memory_manager.get_thread_id(config.get("thread_id"))

            # Create initial LangGraph state
            from OSSS.ai.orchestration.intent_classifier import classify_intent_llm, to_query_profile

            initial_state = create_initial_state(query, execution_id, correlation_id)
            _ensure_effective_queries(initial_state, query)

            # ------------------------------------------------------------
            # Preflight metadata injection (best practice):
            # - nodes consume via execution_state.agent_output_meta
            # ------------------------------------------------------------
            exec_state = initial_state.setdefault("execution_state", {})
            if not isinstance(exec_state, dict):
                initial_state["execution_state"] = {}
                exec_state = initial_state["execution_state"]

            meta = exec_state.setdefault("agent_output_meta", {})
            if not isinstance(meta, dict):
                exec_state["agent_output_meta"] = {}
                meta = exec_state["agent_output_meta"]

            # LLM intent profiling (once per workflow)
            use_llm_intent = bool(config.get("use_llm_intent", False))
            if use_llm_intent:
                intent_result = await classify_intent_llm(query)
                profile = to_query_profile(intent_result)
                meta["_query_profile"] = profile

            # Routing decision (if any) stored once, centrally
            if routing_decision is not None:
                try:
                    if hasattr(routing_decision, "model_dump"):
                        meta["_routing"] = routing_decision.model_dump()  # type: ignore[attr-defined]
                    elif hasattr(routing_decision, "to_dict"):
                        meta["_routing"] = routing_decision.to_dict()  # type: ignore[attr-defined]
                    else:
                        meta["_routing"] = {
                            "selected_agents": getattr(routing_decision, "selected_agents", None),
                            "routing_strategy": getattr(routing_decision, "routing_strategy", None),
                            "confidence_score": getattr(routing_decision, "confidence_score", None),
                        }
                except Exception:
                    meta["_routing"] = {"selected_agents": list(self.agents_to_run or [])}

            # Optional RAG prefetch
            rag_cfg = (config.get("execution_config") or {}).get("rag", {}) if isinstance(config, dict) else {}
            rag_enabled = bool(rag_cfg.get("enabled", False))

            if rag_enabled:
                try:
                    ollama_base = rag_cfg.get("ollama_base", "http://localhost:11434")
                    embed_model = rag_cfg.get("embed_model", "nomic-embed-text")
                    jsonl_path = rag_cfg.get("jsonl_path")
                    top_k = int(rag_cfg.get("top_k", 5))

                    if not jsonl_path:
                        raise ValueError("RAG enabled but execution_config.rag.jsonl_path is missing")

                    rag = await rag_prefetch_jsonl(
                        query,
                        ollama_base=ollama_base,
                        embed_model=embed_model,
                        jsonl_path=jsonl_path,
                        top_k=top_k,
                    )

                    exec_state = initial_state.setdefault("execution_state", {})
                    if not isinstance(exec_state, dict):
                        initial_state["execution_state"] = {}
                        exec_state = initial_state["execution_state"]

                    exec_state["rag_context"] = rag.get("context", "")
                    exec_state["rag_hits"] = rag.get("hits", [])
                    exec_state["rag_enabled"] = True
                    exec_state["rag_meta"] = {
                        "provider": "ollama",
                        "embed_model": embed_model,
                        "jsonl_path": jsonl_path,
                        "top_k": top_k,
                    }

                    self.logger.info(
                        f"[orchestrator] RAG prefetch complete: hits={len(exec_state['rag_hits'])}, top_k={top_k}"
                    )
                except Exception as e:
                    self.logger.warning(f"[orchestrator] RAG prefetch failed (continuing without RAG): {e}")
                    exec_state = initial_state.setdefault("execution_state", {})
                    if isinstance(exec_state, dict):
                        exec_state["rag_enabled"] = False
                        exec_state["rag_error"] = str(e)

            _ensure_effective_queries(initial_state, query)

            if not validate_state_integrity(initial_state):
                raise NodeExecutionError("Initial state validation failed")

            if self.memory_manager.is_enabled():
                self.memory_manager.create_checkpoint(
                    thread_id=thread_id,
                    state=initial_state,
                    agent_step="initialization",
                    metadata={"execution_id": execution_id, "query": query},
                )

            compiled_graph = await self._get_compiled_graph()

            self.logger.info(f"Executing LangGraph StateGraph with thread_id: {thread_id}")

            # Best practice: orchestrator controls node wrapper side-effects (events/logging)
            emit_events = bool(config.get("emit_node_events", False))

            # NOTE: if OSSSContext does not yet include emit_events, remove this line
            context = OSSSContext(
                thread_id=thread_id,
                execution_id=execution_id,
                query=query,
                correlation_id=correlation_id,
                enable_checkpoints=self.enable_checkpoints,
                emit_events=emit_events,  # type: ignore[arg-type]
            )

            final_state = await compiled_graph.ainvoke(initial_state, context=context)

            if not validate_state_integrity(final_state):
                self.logger.warning("Final state validation failed, but proceeding")

            if self.memory_manager.is_enabled():
                self.memory_manager.create_checkpoint(
                    thread_id=thread_id,
                    state=final_state,
                    agent_step="completion",
                    metadata={
                        "execution_id": execution_id,
                        "query": query,
                        "successful_agents": final_state["successful_agents"],
                        "failed_agents": final_state["failed_agents"],
                        "completion_status": "success",
                    },
                )

            agent_context = await self._convert_state_to_context(final_state)

            total_time_ms = (time.time() - start_time) * 1000
            agent_context.execution_state.update(
                {
                    "orchestrator_type": "langgraph-real",
                    "phase": "phase2_1",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "orchestrator_span": orchestrator_span,
                    "thread_id": thread_id,
                    "agents_requested": self.agents_to_run,
                    "config": config,
                    "execution_time_ms": total_time_ms,
                    "langgraph_execution": True,
                    "checkpoints_enabled": self.memory_manager.is_enabled(),
                    "successful_agents_count": len(final_state["successful_agents"]),
                    "failed_agents_count": len(final_state["failed_agents"]),
                    "errors_count": len(final_state["errors"]),
                    "correlation_context": correlation_ctx.to_dict(),
                }
            )

            if final_state["failed_agents"]:
                self.failed_executions += 1
                self.logger.warning(
                    f"LangGraph execution completed with failures: {final_state['failed_agents']}"
                )
            else:
                self.successful_executions += 1

            self.logger.info(
                f"LangGraph execution completed in {total_time_ms:.2f}ms "
                f"(successful: {len(final_state['successful_agents'])}, "
                f"failed: {len(final_state['failed_agents'])})"
            )

            return agent_context

        except Exception as e:
            self.failed_executions += 1
            total_time_ms = (time.time() - start_time) * 1000

            self.logger.error(f"LangGraph execution failed after {total_time_ms:.2f}ms: {e}")

            try:
                await emit_workflow_completed(
                    workflow_id=execution_id,
                    status="failed",
                    execution_time_seconds=total_time_ms / 1000,
                    error_message=str(e),
                    successful_agents=[],
                    failed_agents=self.agents_to_run,
                    error_type=e.__class__.__name__,
                    error_details={
                        "exception_module": e.__class__.__module__,
                        "exception_qualname": getattr(e.__class__, "__qualname__", e.__class__.__name__),
                    },
                    correlation_id=correlation_id,
                    metadata={
                        "orchestrator_type": "langgraph-real",
                        "orchestrator_span": orchestrator_span,
                        "error_type": type(e).__name__,
                    },
                )
            except Exception:
                pass

            error_context = AgentContext(query=query)
            error_context.execution_state.update(
                {
                    "orchestrator_type": "langgraph-real",
                    "phase": "phase2_1",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "orchestrator_span": orchestrator_span,
                    "agents_requested": self.agents_to_run,
                    "config": config,
                    "execution_time_ms": total_time_ms,
                    "langgraph_execution": True,
                    "execution_error": str(e),
                    "execution_error_type": type(e).__name__,
                    "correlation_context": correlation_ctx.to_dict(),
                }
            )

            error_context.add_agent_output(
                "langgraph_error",
                f"LangGraph execution failed: {e}\n"
                f"Execution ID: {execution_id}\n"
                f"Requested agents: {', '.join(self.agents_to_run)}\n"
                f"This indicates an issue with the DAG execution pipeline.",
            )

            raise NodeExecutionError(f"LangGraph execution failed: {e}") from e

    async def _get_compiled_graph(self) -> Any:
        """
        Get or create compiled LangGraph StateGraph using GraphFactory.
        """
        if self._compiled_graph is None:
            self.logger.info("Building LangGraph StateGraph using GraphFactory...")

            try:
                allow_auto_inject_nodes = bool(self._last_config.get("allow_auto_inject_nodes", False))

                # Create graph configuration
                config = GraphConfig(
                    agents_to_run=list(self.agents_to_run or []),
                    enable_checkpoints=self.enable_checkpoints,
                    memory_manager=self.memory_manager,
                    pattern_name="standard",
                    cache_enabled=True,
                    # If your GraphConfig doesn't include this field yet, delete this line.
                    allow_auto_inject_nodes=allow_auto_inject_nodes,  # type: ignore[arg-type]
                )

                # Validate agents before building
                if not self.graph_factory.validate_agents(self.agents_to_run):
                    raise GraphBuildError(f"Invalid agents: {self.agents_to_run}")

                # Create compiled graph using factory
                self._compiled_graph = self.graph_factory.create_graph(config)

                self.logger.info(
                    "Graph built",
                    extra={
                        "pattern": config.pattern_name,
                        "agents_to_run": list(self.agents_to_run or []),
                    },
                )

                self.logger.info(
                    f"Successfully built LangGraph StateGraph with {len(self.agents_to_run)} agents "
                    f"(checkpoints: {self.enable_checkpoints})"
                )

            except GraphBuildError as e:
                self.logger.error(f"Graph building failed: {e}")
                raise NodeExecutionError(f"Failed to build LangGraph StateGraph: {e}") from e
            except Exception as e:
                self.logger.error(f"Unexpected error during graph building: {e}")
                raise NodeExecutionError(f"Failed to build LangGraph StateGraph: {e}") from e

        return self._compiled_graph

    async def _convert_state_to_context(self, final_state: OSSSState) -> AgentContext:
        """
        Convert final LangGraph state back to AgentContext.
        """
        context = AgentContext(query=final_state["query"])

        # Extract structured_outputs
        if "structured_outputs" in final_state:
            context.execution_state["structured_outputs"] = final_state["structured_outputs"]
        else:
            context.execution_state["structured_outputs"] = {}

        # Carry forward per-agent effective queries
        try:
            exec_state = final_state.get("execution_state", {})
            if isinstance(exec_state, dict):
                eff = exec_state.get("effective_queries")
                if isinstance(eff, dict):
                    context.execution_state["effective_queries"] = eff
        except Exception:
            pass

        # Add agent outputs
        if final_state.get("refiner"):
            refiner_output: Optional[RefinerState] = final_state["refiner"]
            if refiner_output is not None:
                context.add_agent_output("refiner", refiner_output["refined_question"])
                context.execution_state["refiner_topics"] = refiner_output["topics"]
                context.execution_state["refiner_confidence"] = refiner_output["confidence"]

        if final_state.get("critic"):
            critic_output: Optional[CriticState] = final_state["critic"]
            if critic_output is not None:
                context.add_agent_output("critic", critic_output["critique"])
                context.execution_state["critic_suggestions"] = critic_output["suggestions"]
                context.execution_state["critic_severity"] = critic_output["severity"]

        if final_state.get("historian"):
            historian_output: Optional[HistorianState] = final_state["historian"]
            if historian_output is not None:
                context.add_agent_output("historian", historian_output["historical_summary"])
                context.execution_state["historian_retrieved_notes"] = historian_output["retrieved_notes"]
                context.execution_state["historian_search_strategy"] = historian_output["search_strategy"]
                context.execution_state["historian_topics_found"] = historian_output["topics_found"]
                context.execution_state["historian_confidence"] = historian_output["confidence"]

        if final_state.get("synthesis"):
            synthesis_output: Optional[SynthesisState] = final_state["synthesis"]
            if synthesis_output is not None:
                context.add_agent_output("synthesis", synthesis_output["final_analysis"])
                context.execution_state["synthesis_insights"] = synthesis_output["key_insights"]
                context.execution_state["synthesis_themes"] = synthesis_output["themes_identified"]

        for agent in final_state["successful_agents"]:
            context.successful_agents.add(agent)

        if final_state["errors"]:
            context.execution_state["langgraph_errors"] = final_state["errors"]

        return context

    def get_execution_statistics(self) -> Dict[str, Any]:
        """
        Get orchestrator execution statistics.
        """
        success_rate = self.successful_executions / self.total_executions if self.total_executions > 0 else 0

        return {
            "orchestrator_type": "langgraph-real",
            "implementation_status": "phase2_production_with_graph_factory",
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "agents_to_run": self.agents_to_run,
            "state_bridge_available": True,
            "checkpoints_enabled": self.enable_checkpoints,
            "dag_structure": "refiner → [critic, historian] → synthesis",
            "graph_factory_stats": self.graph_factory.get_cache_stats(),
            "available_patterns": self.graph_factory.get_available_patterns(),
        }

    def get_dag_structure(self) -> Dict[str, Any]:
        """
        Get information about the DAG structure.
        """
        dependencies = get_node_dependencies()

        return {
            "nodes": self.agents_to_run,
            "dependencies": dependencies,
            "execution_order": ["refiner", "critic", "historian", "synthesis"],
            "parallel_capable": ["critic", "historian"],
            "entry_point": "refiner",
            "terminal_nodes": ["synthesis"],
        }

    async def rollback_to_checkpoint(
        self, thread_id: Optional[str] = None, checkpoint_id: Optional[str] = None
    ) -> Optional[AgentContext]:
        """
        Rollback to a specific checkpoint and return the restored context.
        """
        if not self.memory_manager.is_enabled():
            self.logger.warning("Rollback requested but checkpointing is disabled")
            return None

        target_thread_id = thread_id or self.thread_id
        if not target_thread_id:
            self.logger.error("No thread ID available for rollback")
            return None

        restored_state = self.memory_manager.rollback_to_checkpoint(
            thread_id=target_thread_id, checkpoint_id=checkpoint_id
        )

        if restored_state:
            context = await self._convert_state_to_context(restored_state)
            context.execution_state["rollback_performed"] = True
            context.execution_state["rollback_thread_id"] = target_thread_id
            context.execution_state["rollback_checkpoint_id"] = checkpoint_id

            self.logger.info(f"Successfully rolled back to checkpoint for thread {target_thread_id}")
            return context

        self.logger.warning(f"Rollback failed - no checkpoint found for thread {target_thread_id}")
        return None

    def get_checkpoint_history(self, thread_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get checkpoint history for a thread.
        """
        target_thread_id = thread_id or self.thread_id
        if not target_thread_id:
            return []

        checkpoints = self.memory_manager.get_checkpoint_history(target_thread_id)
        return [
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "timestamp": checkpoint.timestamp.isoformat(),
                "agent_step": checkpoint.agent_step,
                "state_size_bytes": checkpoint.state_size_bytes,
                "success": checkpoint.success,
                "metadata": checkpoint.metadata,
            }
            for checkpoint in checkpoints
        ]

    def get_memory_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive memory and checkpoint statistics.
        """
        memory_stats = self.memory_manager.get_memory_stats()

        orchestrator_stats = {
            "orchestrator_type": "langgraph-real",
            "checkpointing_enabled": self.memory_manager.is_enabled(),
            "current_thread_id": self.thread_id,
            "execution_statistics": self.get_execution_statistics(),
        }

        return {**memory_stats, **orchestrator_stats}

    def cleanup_expired_checkpoints(self) -> int:
        """Clean up expired checkpoints."""
        return self.memory_manager.cleanup_expired_checkpoints()

    def get_graph_cache_stats(self) -> Dict[str, Any]:
        """Get graph factory cache statistics."""
        return self.graph_factory.get_cache_stats()

    def clear_graph_cache(self) -> None:
        """Clear the graph compilation cache."""
        self.graph_factory.clear_cache()
        self.logger.info("Graph compilation cache cleared")

    def get_available_graph_patterns(self) -> List[str]:
        """Get list of available graph patterns."""
        return self.graph_factory.get_available_patterns()

    def set_graph_pattern(self, pattern_name: str) -> None:
        """
        Set the graph pattern for future graph builds.
        """
        if pattern_name not in self.graph_factory.get_available_patterns():
            raise ValueError(
                f"Unknown pattern: {pattern_name}. Available: {self.graph_factory.get_available_patterns()}"
            )

        self._compiled_graph = None
        self._graph = None
        self.logger.info(f"Graph pattern set to: {pattern_name}. Next graph build will use this pattern.")

    async def _make_routing_decision(
        self, query: str, available_agents: List[str], config: Dict[str, Any]
    ) -> "RoutingDecision":
        """
        Make intelligent routing decision using enhanced routing system.
        """
        if not self.context_analyzer:
            raise ValueError("Context analyzer not available for routing decision")
        context_analysis = self.context_analyzer.analyze_context(query)

        performance_data = {}
        for agent in available_agents:
            agent_lower = agent.lower()
            if self.performance_tracker:
                performance_data[agent_lower] = {
                    "success_rate": self.performance_tracker.get_success_rate(agent_lower) or 0.8,
                    "average_time_ms": self.performance_tracker.get_average_time(agent_lower) or 2000.0,
                    "performance_score": self.performance_tracker.get_performance_score(agent_lower),
                }
            else:
                performance_data[agent_lower] = {
                    "success_rate": 0.8,
                    "average_time_ms": 2000.0,
                    "performance_score": 0.7,
                }

        constraints = ResourceConstraints(
            max_execution_time_ms=config.get("max_execution_time_ms"),
            max_agents=config.get("max_agents", 4),
            min_agents=config.get("min_agents", 1),
            min_success_rate=config.get("min_success_rate", 0.7),
        )

        context_requirements = {
            "requires_research": context_analysis.requires_research,
            "requires_criticism": context_analysis.requires_criticism,
            "requires_synthesis": True,
            "requires_refinement": True,
        }

        if not self.resource_optimizer:
            raise ValueError("Resource optimizer not available for routing decision")
        routing_decision = self.resource_optimizer.select_optimal_agents(
            available_agents=available_agents,
            complexity_score=context_analysis.complexity_score,
            performance_data=performance_data,
            constraints=constraints,
            strategy=self.optimization_strategy,
            context_requirements=context_requirements,
        )

        if self.conditional_pattern:
            self.conditional_pattern.update_performance_metrics(
                "routing_decision",
                0.0,
                routing_decision.confidence_score > 0.5,
            )

        return routing_decision

    def update_agent_performance(self, agent: str, duration_ms: float, success: bool) -> None:
        """Update performance metrics for an agent."""
        if self.use_enhanced_routing and self.performance_tracker:
            self.performance_tracker.record_execution(agent, duration_ms, success)

    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get routing system statistics."""
        if not self.use_enhanced_routing:
            return {"enhanced_routing": False}

        stats = {
            "enhanced_routing": True,
            "optimization_strategy": self.optimization_strategy.value,
        }

        if self.conditional_pattern:
            stats.update(self.conditional_pattern.get_routing_statistics())

        return stats
