"""
LangGraph Backend Module

This module provides graph building and compilation services for OSSS's
LangGraph integration. It separates graph construction concerns from execution
orchestration for better maintainability and testability.

Key Components:
- GraphFactory: Core graph building and compilation
- GraphPatterns: Predefined graph structures for common use cases
- GraphCache: Compilation caching for performance optimization
"""

from .build_graph import GraphFactory, GraphBuildError, GraphConfig
from .graph_patterns import (
    GraphPattern,
    StandardPattern,
    ParallelPattern,
    ConditionalPattern,
    PatternRegistry,
)
from .graph_cache import GraphCache, CacheConfig

# ---------------------------------------------------------------------------
# Semantic validation exports
# NOTE: Keep these best-effort to avoid hard crashes on reload if validators
# are optional, renamed, or temporarily broken during development.
# ---------------------------------------------------------------------------
try:
    from .semantic_validation import (
        WorkflowSemanticValidator,
        OSSSValidator,
        SemanticValidationResult,
        ValidationIssue,
        ValidationSeverity,
        ValidationError,
        create_default_validator,
    )
except Exception:  # pragma: no cover
    WorkflowSemanticValidator = None  # type: ignore[assignment]
    OSSSValidator = None  # type: ignore[assignment]
    SemanticValidationResult = None  # type: ignore[assignment]
    ValidationIssue = None  # type: ignore[assignment]
    ValidationSeverity = None  # type: ignore[assignment]
    ValidationError = None  # type: ignore[assignment]

    def create_default_validator(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError(
            "semantic_validation components could not be imported; "
            "check OSSS.ai.langgraph_backend.semantic_validation for errors."
        )

__all__ = [
    # Core graph building
    "GraphFactory",
    "GraphBuildError",
    "GraphConfig",
    # Graph patterns
    "GraphPattern",
    "StandardPattern",
    "ParallelPattern",
    "ConditionalPattern",
    "PatternRegistry",
    # Caching
    "GraphCache",
    "CacheConfig",
    # Semantic validation (best-effort)
    "WorkflowSemanticValidator",
    "OSSSValidator",
    "SemanticValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationError",
    "create_default_validator",
]

__version__ = "2.0.0"  # Phase 2 backend implementation
