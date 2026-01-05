"""
OSSS Orchestration Engine.

This package provides the core orchestration capabilities for OSSS,
including LangGraph integration, node adapters for seamless agent-to-node
conversion, state management, and production DAG execution.

Public API
----------

This module intentionally uses lazy exports via ``__getattr__`` to avoid
import-time cycles (e.g., pulling in ``graph_factory`` / ``node_wrappers``).
"""

from __future__ import annotations

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
    # ✅ Commit 3 (Step 5): extracted services
    "PatternService",
    "PatternServiceConfig",
    "NodeRegistry",
    "GraphAssembler",
    "AssembleInput",
    # -------------------------------------------------------------------------
    # Patterns / routing types (kept for compatibility)
    # -------------------------------------------------------------------------
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

# Freeze to prevent accidental mutation at runtime.
__all__ = tuple(__all__)

# -------------------------------------------------------------------------
# Name groups (keeps __getattr__ tidy and reduces drift)
# -------------------------------------------------------------------------
_LEGACY_GRAPH = {"GraphBuilder", "GraphEdge", "GraphDefinition"}
_LEGACY_ROUTING = {"RoutingFunction", "ConditionalRouter"}
_LEGACY_ADAPTERS = {
    "LangGraphNodeAdapter",
    "StandardNodeAdapter",
    "ConditionalNodeAdapter",
    "ExecutionNodeConfiguration",
    "NodeExecutionResult",
    "create_node_adapter",
}
_LEGACY_DAG = {"PrototypeDAGExecutor", "DAGExecutionResult", "run_prototype_demo"}
_CONFIG = {
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
}

_NEW_BACKEND = {"GraphFactory", "GraphConfig", "GraphBuildError"}
_CACHE = {"CacheConfig"}
_SERVICES = {"PatternService", "PatternServiceConfig", "NodeRegistry", "GraphAssembler", "AssembleInput"}
_PATTERN_TYPES = {"PatternRegistry", "RouterRegistry", "GraphPattern"}
_NODE_WRAPPERS = {
    "refiner_node",
    "data_query_node",
    "critic_node",
    "historian_node",
    "synthesis_node",
    "NodeExecutionError",
    "get_node_dependencies",
}


def __dir__() -> list[str]:
    """
    Improve IDE/autocomplete support for lazy exports.
    """
    return sorted(set(globals().keys()) | set(__all__))


def __getattr__(name: str):
    """
    Lazily resolve orchestration symbols to avoid import-time cycles.

    This ensures that importing `OSSS.ai.orchestration` does not immediately
    pull in heavy or circular modules like `graph_factory` or `node_wrappers`.
    """
    # -------------------------------------------------------------------------
    # Legacy / prototype graph building
    # -------------------------------------------------------------------------
    if name in _LEGACY_GRAPH:
        from .graph_builder import GraphBuilder, GraphEdge, GraphDefinition

        if name == "GraphBuilder":
            return GraphBuilder
        if name == "GraphEdge":
            return GraphEdge
        return GraphDefinition  # name == "GraphDefinition"

    # Routing (legacy/prototype)
    if name in _LEGACY_ROUTING:
        from .routing import RoutingFunction, ConditionalRouter

        if name == "RoutingFunction":
            return RoutingFunction
        return ConditionalRouter  # name == "ConditionalRouter"

    # Node adapters (legacy/prototype)
    if name in _LEGACY_ADAPTERS:
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
        return create_node_adapter  # name == "create_node_adapter"

    # DAG execution (legacy/prototype)
    if name in _LEGACY_DAG:
        from .prototype_dag import (
            PrototypeDAGExecutor,
            DAGExecutionResult,
            run_prototype_demo,
        )

        if name == "PrototypeDAGExecutor":
            return PrototypeDAGExecutor
        if name == "DAGExecutionResult":
            return DAGExecutionResult
        return run_prototype_demo  # name == "run_prototype_demo"

    # Configuration
    if name in _CONFIG:
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
        return reset_orchestration_config  # name == "reset_orchestration_config"

    # -------------------------------------------------------------------------
    # ✅ New LangGraph backend exports
    # -------------------------------------------------------------------------
    if name in _NEW_BACKEND:
        from .graph_factory import GraphFactory, GraphConfig, GraphBuildError

        if name == "GraphFactory":
            return GraphFactory
        if name == "GraphConfig":
            return GraphConfig
        return GraphBuildError  # name == "GraphBuildError"

    if name in _CACHE:
        from .graph_cache import CacheConfig

        return CacheConfig

    if name in _SERVICES:
        if name in {"PatternService", "PatternServiceConfig"}:
            from .pattern_service import PatternService, PatternServiceConfig

            return PatternService if name == "PatternService" else PatternServiceConfig

        if name == "NodeRegistry":
            from .node_registry import NodeRegistry

            return NodeRegistry

        # GraphAssembler / AssembleInput
        from .graph_assembler import GraphAssembler, AssembleInput

        return GraphAssembler if name == "GraphAssembler" else AssembleInput

    # Pattern registries / types (kept for compatibility)
    if name in _PATTERN_TYPES:
        from .patterns.spec import PatternRegistry, RouterRegistry, GraphPattern

        if name == "PatternRegistry":
            return PatternRegistry
        if name == "RouterRegistry":
            return RouterRegistry
        return GraphPattern  # name == "GraphPattern"

    # Node wrappers
    if name in _NODE_WRAPPERS:
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
        return get_node_dependencies  # name == "get_node_dependencies"

    # Keep error message simple and clear.
    raise AttributeError(f"module 'OSSS.ai.orchestration' has no attribute {name!r}")
