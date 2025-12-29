"""
OSSS Orchestration Engine.

This package provides the core orchestration capabilities for OSSS,
including LangGraph integration, node adapters for seamless agent-to-node
conversion, state management, and production DAG execution.
"""

# We keep a single source of truth for the public API here.
__all__ = [
    # -------------------------------------------------------------------------
    # Legacy / prototype graph building
    # -------------------------------------------------------------------------
    "GraphBuilder",
    "GraphEdge",
    "GraphDefinition",
    # Routing (legacy/prototype)
    "RoutingFunction",
    "ConditionalRouter",
    # Node adapters (legacy/prototype)
    "LangGraphNodeAdapter",
    "StandardNodeAdapter",
    "ConditionalNodeAdapter",
    "ExecutionNodeConfiguration",
    "NodeExecutionResult",
    "create_node_adapter",
    # DAG execution (legacy/prototype)
    "PrototypeDAGExecutor",
    "DAGExecutionResult",
    "run_prototype_demo",
    # Configuration
    "LangGraphIntegrationConfig",
    "DAGExecutionConfig",
    "NodeExecutionConfig",
    "LangGraphConfigManager",
    "ExecutionMode",
    "OrchestrationValidationLevel",
    "FailurePolicy",
    "get_orchestration_config",
    "set_orchestration_config",
    "reset_orchestration_config",
    # -------------------------------------------------------------------------
    # ✅ New LangGraph backend exports
    # -------------------------------------------------------------------------
    "GraphFactory",
    "GraphConfig",
    "GraphBuildError",
    "CacheConfig",
    "PatternRegistry",
    "RouterRegistry",
    "GraphPattern",
    # Node wrappers
    "refiner_node",
    "data_query_node",
    "critic_node",
    "historian_node",
    "synthesis_node",
    "NodeExecutionError",
    "get_node_dependencies",
]


def __getattr__(name: str):
    """
    Lazily resolve orchestration symbols to avoid import-time cycles.

    This ensures that importing `OSSS.ai.orchestration` does not immediately
    pull in heavy or circular modules like `graph_factory` or `node_wrappers`.
    """
    # -------------------------------------------------------------------------
    # Legacy / prototype graph building
    # -------------------------------------------------------------------------
    if name in {"GraphBuilder", "GraphEdge", "GraphDefinition"}:
        from .graph_builder import GraphBuilder, GraphEdge, GraphDefinition

        if name == "GraphBuilder":
            return GraphBuilder
        if name == "GraphEdge":
            return GraphEdge
        if name == "GraphDefinition":
            return GraphDefinition

    # Routing (legacy/prototype)
    if name in {"RoutingFunction", "ConditionalRouter"}:
        from .routing import RoutingFunction, ConditionalRouter

        if name == "RoutingFunction":
            return RoutingFunction
        if name == "ConditionalRouter":
            return ConditionalRouter

    # Node adapters (legacy/prototype)
    if name in {
        "LangGraphNodeAdapter",
        "StandardNodeAdapter",
        "ConditionalNodeAdapter",
        "ExecutionNodeConfiguration",
        "NodeExecutionResult",
        "create_node_adapter",
    }:
        from .adapter import (
            LangGraphNodeAdapter,
            StandardNodeAdapter,
            ConditionalNodeAdapter,
            ExecutionNodeConfiguration,
            NodeExecutionResult,
            create_node_adapter,
        )

        if name == "LangGraphNodeAdapter":
            return LangGraphNodeAdapter
        if name == "StandardNodeAdapter":
            return StandardNodeAdapter
        if name == "ConditionalNodeAdapter":
            return ConditionalNodeAdapter
        if name == "ExecutionNodeConfiguration":
            return ExecutionNodeConfiguration
        if name == "NodeExecutionResult":
            return NodeExecutionResult
        if name == "create_node_adapter":
            return create_node_adapter

    # DAG execution (legacy/prototype)
    if name in {"PrototypeDAGExecutor", "DAGExecutionResult", "run_prototype_demo"}:
        from .prototype_dag import (
            PrototypeDAGExecutor,
            DAGExecutionResult,
            run_prototype_demo,
        )

        if name == "PrototypeDAGExecutor":
            return PrototypeDAGExecutor
        if name == "DAGExecutionResult":
            return DAGExecutionResult
        if name == "run_prototype_demo":
            return run_prototype_demo

    # Configuration
    if name in {
        "LangGraphIntegrationConfig",
        "DAGExecutionConfig",
        "NodeExecutionConfig",
        "LangGraphConfigManager",
        "ExecutionMode",
        "OrchestrationValidationLevel",
        "FailurePolicy",
        "get_orchestration_config",
        "set_orchestration_config",
        "reset_orchestration_config",
    }:
        from .config import (
            LangGraphIntegrationConfig,
            DAGExecutionConfig,
            NodeExecutionConfig,
            LangGraphConfigManager,
            ExecutionMode,
            OrchestrationValidationLevel,
            FailurePolicy,
            get_orchestration_config,
            set_orchestration_config,
            reset_orchestration_config,
        )

        if name == "LangGraphIntegrationConfig":
            return LangGraphIntegrationConfig
        if name == "DAGExecutionConfig":
            return DAGExecutionConfig
        if name == "NodeExecutionConfig":
            return NodeExecutionConfig
        if name == "LangGraphConfigManager":
            return LangGraphConfigManager
        if name == "ExecutionMode":
            return ExecutionMode
        if name == "OrchestrationValidationLevel":
            return OrchestrationValidationLevel
        if name == "FailurePolicy":
            return FailurePolicy
        if name == "get_orchestration_config":
            return get_orchestration_config
        if name == "set_orchestration_config":
            return set_orchestration_config
        if name == "reset_orchestration_config":
            return reset_orchestration_config

    # -------------------------------------------------------------------------
    # ✅ New LangGraph backend exports
    # -------------------------------------------------------------------------

    # GraphFactory + config
    if name in {"GraphFactory", "GraphConfig", "GraphBuildError"}:
        from .graph_factory import GraphFactory, GraphConfig, GraphBuildError

        if name == "GraphFactory":
            return GraphFactory
        if name == "GraphConfig":
            return GraphConfig
        if name == "GraphBuildError":
            return GraphBuildError

    # CacheConfig
    if name == "CacheConfig":
        from .graph_cache import CacheConfig

        return CacheConfig

    # Pattern registries / types
    if name in {"PatternRegistry", "RouterRegistry", "GraphPattern"}:
        from .patterns.spec import PatternRegistry, RouterRegistry, GraphPattern

        if name == "PatternRegistry":
            return PatternRegistry
        if name == "RouterRegistry":
            return RouterRegistry
        if name == "GraphPattern":
            return GraphPattern

    # Node wrappers
    if name in {
        "refiner_node",
        "data_query_node",
        "critic_node",
        "historian_node",
        "synthesis_node",
        "NodeExecutionError",
        "get_node_dependencies",
    }:
        from .node_wrappers import (
            refiner_node,
            data_query_node,
            critic_node,
            historian_node,
            synthesis_node,
            NodeExecutionError,
            get_node_dependencies,
        )

        if name == "refiner_node":
            return refiner_node
        if name == "data_query_node":
            return data_query_node
        if name == "critic_node":
            return critic_node
        if name == "historian_node":
            return historian_node
        if name == "synthesis_node":
            return synthesis_node
        if name == "NodeExecutionError":
            return NodeExecutionError
        if name == "get_node_dependencies":
            return get_node_dependencies

    raise AttributeError(f"module 'OSSS.ai.orchestration' has no attribute {name!r}")
