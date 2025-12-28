"""
Base Advanced Node Infrastructure for OSSS.

This module provides the foundation for advanced node types including
DECISION, AGGREGATOR, VALIDATOR, and TERMINATOR nodes. It defines
the base abstractions and execution context for all advanced nodes.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict, model_validator
from OSSS.ai.agents.metadata import AgentMetadata, TaskClassification


class NodeExecutionContext(BaseModel):
    """
    Execution context for advanced nodes.

    Relaxed to align with LangGraph/AgentContext:
    - Accepts `query` and `execution_state`
    - Allows extra keys (extra="allow")
    - task_classification / cognitive_classification are optional
      and validated at node level.
    """

    # Core identifiers (can be filled by router; validated later)
    correlation_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for request correlation",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "req-123e4567-e89b-12d3-a456-426614174000"},
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for the workflow",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "wf-123e4567-e89b-12d3-a456-426614174000"},
    )

    # NEW: raw query + orchestration state (matches your logs)
    query: Optional[str] = Field(
        default=None,
        description="Original user query text, if available",
    )
    execution_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Shared execution state passed along the graph",
    )

    # Classification info – optional here, enforced in validate_context
    cognitive_classification: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Multi-axis cognitive classification metadata",
        json_schema_extra={"example": {"domain": "data_systems", "topic": "website content"}},
    )
    task_classification: Optional[TaskClassification] = Field(
        default=None,
        description="Task classification for execution",
    )

    # Optional fields with defaults
    execution_path: List[str] = Field(
        default_factory=list,
        description="Path of nodes executed so far",
        max_length=100,
        json_schema_extra={"example": ["refiner", "critic", "historian"]},
    )
    confidence_score: Optional[float] = Field(
        default=None,
        description="Confidence score for the execution context",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.85},
    )
    resource_usage: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Resource usage metrics and tracking",
        json_schema_extra={"example": {"cpu_usage": 45.2, "memory_mb": 128.5}},
    )

    # Metadata for advanced routing
    previous_nodes: List[str] = Field(
        default_factory=list,
        description="List of previously executed nodes",
        max_length=100,
        json_schema_extra={"example": ["refiner", "critic"]},
    )
    available_inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Available inputs from previous nodes",
        json_schema_extra={"example": {"refiner_final": "refined query"}},
    )
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata",
        json_schema_extra={"example": {"priority": "high", "timeout_ms": 30000}},
    )

    model_config = ConfigDict(
        extra="allow",                 # <-- important: accept query, execution_state, etc.
        validate_assignment=True,
        arbitrary_types_allowed=True,  # For TaskClassification and datetime objects
    )

    @model_validator(mode="after")
    def initialize_defaults_and_validate(self) -> "NodeExecutionContext":
        """Initialize default values and validate context."""
        if self.resource_usage is None:
            self.resource_usage = {}

        if self.resource_usage is not None and "start_time" not in self.resource_usage:
            self.resource_usage.update({"start_time": datetime.now(timezone.utc)})

        # Optionally: if classification only exists in execution_state, surface it:
        exec_state = self.execution_state or {}
        if self.task_classification is None and "task_classification" in exec_state:
            self.task_classification = exec_state["task_classification"]  # type: ignore[assignment]
        if self.cognitive_classification is None and "cognitive_classification" in exec_state:
            self.cognitive_classification = exec_state["cognitive_classification"]  # type: ignore[assignment]

        return self

    def add_to_execution_path(self, node_name: str) -> None:
        """Add a node to the execution path."""
        self.execution_path.append(node_name)
        self.previous_nodes.append(node_name)

    def update_resource_usage(self, metrics: Dict[str, Any]) -> None:
        """Update resource usage metrics."""
        if self.resource_usage is not None:
            self.resource_usage.update(metrics)

    def get_execution_time_ms(self) -> Optional[float]:
        """Calculate execution time in milliseconds if start_time is available."""
        if (
            self.resource_usage is not None
            and "start_time" in self.resource_usage
            and "end_time" in self.resource_usage
        ):
            start = self.resource_usage["start_time"]
            end = self.resource_usage["end_time"]

            # Type safety: ensure we have datetime objects before calculating
            if isinstance(start, datetime) and isinstance(end, datetime):
                return (end - start).total_seconds() * 1000.0

        return None

    def has_input_from(self, node_name: str) -> bool:
        """Check if context has input from a specific node."""
        return node_name in self.available_inputs

    def get_input_from(self, node_name: str) -> Optional[Any]:
        """Get input from a specific node if available."""
        return self.available_inputs.get(node_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization.

        Note: This method is kept for backward compatibility.
        For new code, use model_dump() instead.
        """
        data = self.model_dump()
        # Handle special serialization for TaskClassification
        if hasattr(self.task_classification, "to_dict"):
            data["task_classification"] = self.task_classification.to_dict()
        return data


class BaseAdvancedNode(ABC):
    """
    Base class for all advanced node types.

    This abstract class defines the interface and common functionality for
    DECISION, AGGREGATOR, VALIDATOR, and TERMINATOR nodes. Each node type
    must implement the execute and can_handle methods.
    """

    def __init__(self, metadata: AgentMetadata, node_name: str) -> None:
        """
        Initialize the advanced node.

        Parameters
        ----------
        metadata : AgentMetadata
            The agent metadata containing multi-axis classification
        node_name : str
            Unique name for this node instance
        """
        self.metadata = metadata
        self.node_name = node_name
        self.execution_pattern = metadata.execution_pattern

        # Validate execution pattern
        valid_patterns = {
            "processor",
            "decision",
            "aggregator",
            "validator",
            "terminator",
        }
        if self.execution_pattern not in valid_patterns:
            raise ValueError(
                f"Invalid execution pattern '{self.execution_pattern}'. "
                f"Must be one of: {valid_patterns}"
            )

    @abstractmethod
    async def execute(self, context: NodeExecutionContext) -> Dict[str, Any]:
        """
        Execute the node logic.

        Parameters
        ----------
        context : NodeExecutionContext
            The execution context containing all necessary information

        Returns
        -------
        Dict[str, Any]
            The execution result containing output data and metadata
        """
        pass

    @abstractmethod
    def can_handle(self, context: NodeExecutionContext) -> bool:
        """
        Check if this node can handle the given context.

        This method should evaluate the context against the node's
        requirements and capabilities to determine if execution is possible.

        Parameters
        ----------
        context : NodeExecutionContext
            The execution context to evaluate

        Returns
        -------
        bool
            True if the node can handle the context, False otherwise
        """
        pass

    def get_fallback_patterns(self) -> List[str]:
        """
        Get fallback execution patterns for this node.

        Returns a list of execution patterns that can be used as fallbacks
        if this node fails or cannot handle the context.

        Returns
        -------
        List[str]
            List of fallback execution pattern names
        """
        FALLBACK_PATTERNS = {
            "decision": ["processor", "terminator"],
            "aggregator": ["processor", "validator"],
            "validator": ["processor", "terminator"],
            "processor": ["terminator"],
            "terminator": [],
        }
        return FALLBACK_PATTERNS.get(self.execution_pattern, [])

    def get_node_info(self) -> Dict[str, Any]:
        """
        Get information about this node.

        Returns
        -------
        Dict[str, Any]
            Node information including name, type, and metadata
        """
        return {
            "node_name": self.node_name,
            "execution_pattern": self.execution_pattern,
            "cognitive_speed": self.metadata.cognitive_speed,
            "cognitive_depth": self.metadata.cognitive_depth,
            "processing_pattern": self.metadata.processing_pattern,
            "pipeline_role": self.metadata.pipeline_role,
            "bounded_context": self.metadata.bounded_context,
            "capabilities": self.metadata.capabilities,
            "fallback_patterns": self.get_fallback_patterns(),
        }

    def validate_context(self, context: NodeExecutionContext) -> List[str]:
        """
        Validate that required context elements are present.

        This version SAFELY falls back to execution_state if the
        root-level fields are not populated yet, allowing the
        DecisionNode to operate even when classification is stored
        only in execution_state.
        """
        errors = []

        exec_state = getattr(context, "execution_state", {}) or {}

        # ---- FALLBACK HYDRATION (Option B) ----
        task = context.task_classification or context.execution_state.get("task_classification")
        cognitive = context.cognitive_classification or context.execution_state.get("cognitive_classification")

        # ---- VALIDATION ----
        if not task:
            errors.append(
                "Missing task_classification in context "
                "(neither root nor execution_state.task_classification set)"
            )

        if not cognitive:
            errors.append(
                "Missing cognitive_classification in context "
                "(neither root nor execution_state.cognitive_classification set)"
            )


        # ---- OPTIONAL STATE HYDRATION ----
        if task and not getattr(context, "task_classification", None):
            context.task_classification = task
        if cognitive and not getattr(context, "cognitive_classification", None):
            context.cognitive_classification = cognitive

        return errors


    async def pre_execute(self, context: NodeExecutionContext) -> None:
        """
        Hook for pre-execution setup.

        Override this method to perform any setup required before execution.
        Default implementation adds the node to the execution path.

        Parameters
        ----------
        context : NodeExecutionContext
            The execution context
        """
        context.add_to_execution_path(self.node_name)

    async def post_execute(
        self, context: NodeExecutionContext, result: Dict[str, Any]
    ) -> None:
        """
        Hook for post-execution cleanup.

        Override this method to perform any cleanup after execution.
        Default implementation updates resource usage with end time.

        Parameters
        ----------
        context : NodeExecutionContext
            The execution context
        result : Dict[str, Any]
            The execution result
        """
        context.update_resource_usage({"end_time": datetime.now(timezone.utc)})

    def __repr__(self) -> str:
        """String representation of the node."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.node_name}', "
            f"pattern='{self.execution_pattern}')"
        )