"""
OSSS Orchestration Engine.

This package provides the core orchestration capabilities for OSSS,
including LangGraph integration, node adapters for seamless agent-to-node
conversion, state management, and production DAG execution.
"""

# -----------------------------------------------------------------------------
# Legacy / prototype orchestration exports (kept for compatibility)
# -----------------------------------------------------------------------------

from .graph_factory import GraphFactory, GraphConfig, GraphBuildError
from .graph_cache import CacheConfig
from .graph_builder import GraphBuilder, GraphEdge, GraphDefinition
from .routing import RoutingFunction, ConditionalRouter
from .adapter import (
    LangGraphNodeAdapter,
    StandardNodeAdapter,
    ConditionalNodeAdapter,
    ExecutionNodeConfiguration,
    NodeExecutionResult,
    create_node_adapter,
)
from .prototype_dag import PrototypeDAGExecutor, DAGExecutionResult, run_prototype_demo
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

# -----------------------------------------------------------------------------
# ✅ New LangGraph backend (JSON-driven patterns + routers)
# Keep these re-exports so other packages can import from OSSS.ai.orchestration.
# -----------------------------------------------------------------------------

# Optional: re-export pattern registries/types if you want them reachable here
from .patterns.spec import PatternRegistry, RouterRegistry, GraphPattern

# Node wrappers (commonly needed by callers / tests)
from .node_wrappers import (
    refiner_node,
    data_query_node,
    critic_node,
    historian_node,
    synthesis_node,
    NodeExecutionError,
    get_node_dependencies,
)

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
    "CacheConfig"
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
