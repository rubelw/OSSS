"""
Unified Agent Metadata with Multi-Axis Classification.

This module consolidates agent metadata from registry.py and dynamic_composition.py
while adding the multi-axis classification system needed for event-driven architecture
and future utility agent integration.
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Type, Literal, TYPE_CHECKING, cast
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator

if TYPE_CHECKING:
    from OSSS.ai.agents.base_agent import BaseAgent

from OSSS.ai.agents.protocols import AgentConstructorPattern
from OSSS.ai.exceptions import FailurePropagationStrategy
from OSSS.ai.dependencies.dynamic_composition import DiscoveryStrategy


class AgentMetadata(BaseModel):
    """
    Unified agent metadata with multi-axis classification.

    Combines functionality from registry-based agent management with
    dynamic discovery capabilities and adds multi-axis classification
    for intelligent event routing and service extraction.
    """

    # Core identification (from registry.py)
    name: str = Field(
        ...,
        description="Unique name for the agent",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "refiner"},
    )
    agent_class: Any = Field(
        ...,
        description="The agent class type for instantiation",
        json_schema_extra={"example": "OSSS.ai.agents.refiner.agent.RefinerAgent"},
    )
    description: str = Field(
        "",
        description="Human-readable description of the agent",
        max_length=1000,
        json_schema_extra={
            "example": "Refines and improves user queries for better processing"
        },
    )

    # Multi-axis classification (new for event-driven architecture)
    cognitive_speed: Literal["fast", "slow", "adaptive"] = Field(
        "adaptive",
        description="Cognitive processing speed classification",
        json_schema_extra={"example": "adaptive"},
    )
    cognitive_depth: Literal["shallow", "deep", "variable"] = Field(
        "variable",
        description="Cognitive processing depth classification",
        json_schema_extra={"example": "variable"},
    )
    processing_pattern: Literal["atomic", "composite", "chain"] = Field(
        "atomic",
        description="Processing pattern classification",
        json_schema_extra={"example": "atomic"},
    )
    execution_pattern: Literal[
        "processor", "decision", "aggregator", "validator", "terminator"
    ] = Field(
        "processor",
        description="Execution pattern classification for advanced node types",
        json_schema_extra={"example": "processor"},
    )
    primary_capability: str = Field(
        "",
        description="Primary capability identifier",
        max_length=100,
        json_schema_extra={"example": "critical_analysis"},
    )
    secondary_capabilities: List[str] = Field(
        default_factory=list,
        description="List of secondary capabilities",
        json_schema_extra={"example": ["bias_detection", "assumption_identification"]},
    )
    pipeline_role: Literal["entry", "intermediate", "terminal", "standalone"] = Field(
        "standalone",
        description="Role in the processing pipeline",
        json_schema_extra={"example": "intermediate"},
    )
    bounded_context: str = Field(
        "reflection",
        description="Bounded context classification",
        pattern=r"^(reflection|transformation|retrieval)$",
        json_schema_extra={"example": "reflection"},
    )

    # Runtime and execution (from registry.py)
    requires_llm: bool = Field(
        False,
        description="Whether this agent requires an LLM interface",
        json_schema_extra={"example": True},
    )
    constructor_pattern: "AgentConstructorPattern" = Field(
        AgentConstructorPattern.FLEXIBLE,
        description="Constructor pattern for type-safe agent instantiation",
        json_schema_extra={"example": "llm_required"},
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of agent dependencies",
        json_schema_extra={"example": ["refiner"]},
    )
    is_critical: bool = Field(
        True,
        description="Whether this agent is critical for workflow execution",
        json_schema_extra={"example": True},
    )
    failure_strategy: FailurePropagationStrategy = Field(
        FailurePropagationStrategy.FAIL_FAST,
        description="Strategy for handling agent failures",
        json_schema_extra={"example": "FAIL_FAST"},
    )
    fallback_agents: List[str] = Field(
        default_factory=list,
        description="List of fallback agents if this agent fails",
        json_schema_extra={"example": ["backup_critic"]},
    )
    health_checks: List[str] = Field(
        default_factory=list,
        description="List of health check identifiers",
        json_schema_extra={"example": ["llm_connectivity", "memory_usage"]},
    )

    # Capabilities and versioning (from dynamic_composition.py)
    version: str = Field(
        "1.0.0",
        description="Agent version using semantic versioning",
        pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$",
        json_schema_extra={"example": "1.2.0"},
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of technical capabilities",
        json_schema_extra={"example": ["llm_integration", "critical_analysis"]},
    )
    resource_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resource requirements for agent execution",
        json_schema_extra={"example": {"memory_mb": 512, "cpu_cores": 1}},
    )
    compatibility: Dict[str, str] = Field(
        default_factory=dict,
        description="Compatibility constraints and requirements",
        json_schema_extra={"example": {"min_version": "1.0.0", "max_version": "2.0.0"}},
    )

    # Discovery metadata (from dynamic_composition.py)
    agent_id: Optional[str] = Field(
        None,
        description="Unique agent identifier (defaults to name)",
        max_length=100,
        json_schema_extra={"example": "refiner-001"},
    )
    module_path: Optional[str] = Field(
        None,
        description="Python module path for the agent class",
        max_length=500,
        json_schema_extra={"example": "OSSS.ai.agents.refiner.agent.RefinerAgent"},
    )
    discovered_at: float = Field(
        default_factory=time.time,
        description="Timestamp when agent was discovered",
        ge=0.0,
        json_schema_extra={"example": 1640995200.0},
    )
    discovery_strategy: Optional[DiscoveryStrategy] = Field(
        None,
        description="Strategy used to discover this agent",
        json_schema_extra={"example": "registry"},
    )
    file_path: Optional[Path] = Field(
        None,
        description="File system path to agent source",
        json_schema_extra={"example": "/path/to/agent.py"},
    )
    checksum: Optional[str] = Field(
        None,
        description="Checksum for agent source verification",
        max_length=100,
        json_schema_extra={"example": "sha256:abc123..."},
    )

    # Runtime state (from dynamic_composition.py)
    load_count: int = Field(
        0,
        description="Number of times agent has been loaded",
        ge=0,
        json_schema_extra={"example": 5},
    )
    last_loaded: Optional[float] = Field(
        None,
        description="Timestamp of last agent load",
        ge=0.0,
        json_schema_extra={"example": 1640995200.0},
    )
    load_errors: List[str] = Field(
        default_factory=list,
        description="List of load error messages",
        json_schema_extra={"example": ["Import error: module not found"]},
    )
    is_loaded: bool = Field(
        False,
        description="Whether agent is currently loaded",
        json_schema_extra={"example": True},
    )

    @field_validator(
        "secondary_capabilities",
        "dependencies",
        "fallback_agents",
        "health_checks",
        "capabilities",
        "load_errors",
    )
    @classmethod
    def validate_string_lists(cls, v: Any) -> Any:
        """Validate string list fields."""
        if not isinstance(v, list):
            raise ValueError("Must be a list")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("All items must be strings")
        return v

    @field_validator("agent_class", mode="before")
    @classmethod
    def validate_agent_class(cls, v: Any) -> Any:
        """Handle agent_class validation and conversion from string."""
        # Handle Mock objects (for testing) - check for any mock-like object
        if (
            hasattr(v, "_mock_name")
            or str(type(v)).startswith("<class 'unittest.mock.")
            or hasattr(v, "_mock_methods")
            or str(type(v).__name__) in ("Mock", "MagicMock")
        ):
            # This is a Mock object, accept it as-is for testing
            # Ensure it has the required attributes
            if not hasattr(v, "__module__"):
                v.__module__ = "test.module"
            if not hasattr(v, "__name__"):
                v.__name__ = "MockAgent"
            return v

        if isinstance(v, str):
            # Convert string representation back to actual class
            try:
                module_name, class_name = v.rsplit(".", 1)
                import importlib

                module = importlib.import_module(module_name)
                return getattr(module, class_name)
            except (ValueError, ImportError, AttributeError):
                # Fallback to dummy agent for invalid class paths
                class StringConversionFallbackAgent:
                    """Fallback agent class for invalid class paths during string-to-class conversion."""

                    __module__ = "OSSS.ai.agents.dummy"
                    __name__ = "StringConversionFallbackAgent"

                    def __init__(self) -> None:
                        self.name = "dummy_agent"

                    async def invoke(
                        self, state: Any, config: Optional[Dict[str, Any]] = None
                    ) -> Any:
                        del config  # Mark as used
                        return state

                return StringConversionFallbackAgent
        return v

    def model_post_init(self, __context: Any) -> None:
        """Initialize derived fields and defaults."""
        # Set agent_id from name if not provided
        if self.agent_id is None:
            self.agent_id = self.name

        # Set module_path from agent_class if not provided
        if self.module_path is None and self.agent_class:
            self.module_path = (
                f"{self.agent_class.__module__}.{self.agent_class.__name__}"
            )

        # Derive primary_capability from name if not set
        if not self.primary_capability:
            self.primary_capability = self._derive_capability_from_name()

        # Initialize capabilities list if empty
        if not self.capabilities:
            self.capabilities = self._derive_capabilities()

    def _derive_capability_from_name(self) -> str:
        """Derive primary capability from agent name."""
        capability_map = {
            "refiner": "intent_clarification",
            "critic": "critical_analysis",
            "historian": "context_retrieval",
            "synthesis": "multi_perspective_synthesis",
            "translator": "translation",
            "summarizer": "summarization",
            "formatter": "output_formatting",
        }
        return capability_map.get(self.name.lower(), self.name.lower())

    def _derive_capabilities(self) -> List[str]:
        """Derive technical capabilities list from agent characteristics."""
        caps = [self.primary_capability]

        # Add capabilities based on agent characteristics
        if self.requires_llm:
            caps.append("llm_integration")

        if self.processing_pattern == "composite":
            caps.append("multi_step_processing")

        if self.pipeline_role == "entry":
            caps.append("input_processing")
        elif self.pipeline_role == "terminal":
            caps.append("output_generation")

        return caps

    def can_replace(self, other: "AgentMetadata") -> bool:
        """
        Check if this agent can replace another agent.

        Uses both capability matching and version compatibility.
        """
        if self.agent_id != other.agent_id:
            return False

        # Check version compatibility
        if "min_version" in other.compatibility:
            min_version = other.compatibility["min_version"]
            if self.version < min_version:
                return False

        # Check primary capability match
        if self.primary_capability != other.primary_capability:
            return False

        # Check that all required capabilities are present
        for required_cap in other.capabilities:
            if required_cap not in self.capabilities:
                return False

        return True

    def is_compatible_with_task(
        self, task_type: str, domain: Optional[str] = None
    ) -> bool:
        """
        Check if this agent is compatible with a specific task type.

        Args:
            task_type: Type of task ("transform", "evaluate", "retrieve", etc.)
            domain: Optional domain specialization

        Returns:
            True if agent can handle this task type
        """
        # domain parameter is available for future use but not currently used
        del domain
        # Map task types to capabilities
        task_capability_map = {
            "transform": ["translation", "summarization", "output_formatting"],
            "evaluate": [
                "critical_analysis",
                "bias_detection",
                "assumption_identification",
            ],
            "retrieve": ["context_retrieval", "memory_search", "information_gathering"],
            "synthesize": ["multi_perspective_synthesis", "conflict_resolution"],
            "clarify": ["intent_clarification", "prompt_structuring"],
            "format": ["output_formatting", "structure_generation"],
        }

        compatible_capabilities = task_capability_map.get(task_type, [])

        # Check if agent has any compatible capability
        agent_capabilities = [self.primary_capability] + self.secondary_capabilities
        return any(cap in agent_capabilities for cap in compatible_capabilities)

    def get_performance_tier(self) -> str:
        """
        Get performance tier based on cognitive characteristics.

        Returns:
            Performance tier: "fast", "balanced", "thorough"
        """
        if self.cognitive_speed == "fast" and self.cognitive_depth == "shallow":
            return "fast"
        elif self.cognitive_speed == "slow" and self.cognitive_depth == "deep":
            return "thorough"
        else:
            return "balanced"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for serialization."""
        return {
            # Core identification
            "name": self.name,
            "agent_class": f"{self.agent_class.__module__}.{self.agent_class.__name__}",
            "description": self.description,
            # Multi-axis classification
            "cognitive_speed": self.cognitive_speed,
            "cognitive_depth": self.cognitive_depth,
            "processing_pattern": self.processing_pattern,
            "execution_pattern": self.execution_pattern,
            "primary_capability": self.primary_capability,
            "secondary_capabilities": self.secondary_capabilities,
            "pipeline_role": self.pipeline_role,
            "bounded_context": self.bounded_context,
            # Runtime and execution
            "requires_llm": self.requires_llm,
            "dependencies": self.dependencies,
            "is_critical": self.is_critical,
            "failure_strategy": self.failure_strategy.value,
            "fallback_agents": self.fallback_agents,
            "health_checks": self.health_checks,
            # Capabilities and versioning
            "version": self.version,
            "capabilities": self.capabilities,
            "resource_requirements": self.resource_requirements,
            "compatibility": self.compatibility,
            # Discovery metadata
            "agent_id": self.agent_id,
            "module_path": self.module_path,
            "discovered_at": self.discovered_at,
            "discovery_strategy": (
                self.discovery_strategy.value if self.discovery_strategy else None
            ),
            "file_path": str(self.file_path) if self.file_path else None,
            "checksum": self.checksum,
            # Runtime state
            "load_count": self.load_count,
            "last_loaded": self.last_loaded,
            "is_loaded": self.is_loaded,
            "load_errors": self.load_errors,
        }

    @classmethod
    def create_for_registry(
        cls,
        name: str,
        agent_class: "Type[BaseAgent]",
        requires_llm: bool = False,
        constructor_pattern: Optional["AgentConstructorPattern"] = None,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        is_critical: bool = True,
        failure_strategy: FailurePropagationStrategy = FailurePropagationStrategy.FAIL_FAST,
        fallback_agents: Optional[List[str]] = None,
        health_checks: Optional[List[str]] = None,
        cognitive_speed: Literal["fast", "slow", "adaptive"] = "adaptive",
        cognitive_depth: Literal["shallow", "deep", "variable"] = "variable",
        processing_pattern: Literal["atomic", "composite", "chain"] = "atomic",
        primary_capability: str = "",
        secondary_capabilities: Optional[List[str]] = None,
        pipeline_role: Literal[
            "entry", "intermediate", "terminal", "standalone"
        ] = "standalone",
        bounded_context: str = "reflection",
    ) -> "AgentMetadata":
        """
        Create AgentMetadata for registry registration.

        This factory method properly handles None values for list fields,
        letting Pydantic handle default_factory creation instead of manually
        constructing empty lists.
        """
        # Build kwargs dict, only including non-None values for list fields
        kwargs = {
            "name": name,
            "agent_class": agent_class,
            "requires_llm": requires_llm,
            "description": description,
            "is_critical": is_critical,
            "failure_strategy": failure_strategy,
            "cognitive_speed": cognitive_speed,
            "cognitive_depth": cognitive_depth,
            "processing_pattern": processing_pattern,
            "primary_capability": primary_capability,
            "pipeline_role": pipeline_role,
            "bounded_context": bounded_context,
        }

        # Handle constructor_pattern (if provided)
        if constructor_pattern is not None:
            kwargs["constructor_pattern"] = constructor_pattern

        # Only add list fields if they are not None
        if dependencies is not None:
            kwargs["dependencies"] = dependencies
        if fallback_agents is not None:
            kwargs["fallback_agents"] = fallback_agents
        if health_checks is not None:
            kwargs["health_checks"] = health_checks
        if secondary_capabilities is not None:
            kwargs["secondary_capabilities"] = secondary_capabilities

        return cls(**kwargs)

    @classmethod
    def create_default(
        cls,
        name: str = "default_agent",
        agent_class: Optional[Type[Any]] = None,
        description: str = "Default agent metadata",
    ) -> "AgentMetadata":
        """
        Create default agent metadata.
        """
        if agent_class is None:
            # Import BaseAgent at runtime to avoid circular import
            import importlib
            from typing import TYPE_CHECKING, Optional, Dict

            try:
                base_agent_module = importlib.import_module(
                    "OSSS.ai.agents.base_agent"
                )
                agent_class = base_agent_module.BaseAgent
            except ImportError:
                # Create a simple dummy class as fallback
                class EqualityFallbackAgent:
                    """Fallback agent class for equality comparison when BaseAgent cannot be imported."""

                    def __init__(self) -> None:
                        self.name = "dummy_agent"

                    async def invoke(
                        self, state: Any, config: Optional[Dict[str, Any]] = None
                    ) -> Any:
                        """Dummy invoke method with proper BaseAgent signature."""
                        del config  # Mark as used
                        return state

                    @property
                    def metadata(self) -> "AgentMetadata":
                        """Return minimal metadata."""
                        from OSSS.ai.exceptions import FailurePropagationStrategy

                        return cls(
                            name="dummy_agent",
                            agent_class=EqualityFallbackAgent,
                            description="Dummy agent metadata",
                            cognitive_speed="adaptive",
                            cognitive_depth="variable",
                            processing_pattern="atomic",
                            execution_pattern="processor",
                            primary_capability="dummy_processing",
                            secondary_capabilities=[],
                            pipeline_role="standalone",
                            bounded_context="reflection",
                            requires_llm=False,
                            constructor_pattern=AgentConstructorPattern.FLEXIBLE,
                            dependencies=[],
                            is_critical=False,
                            failure_strategy=FailurePropagationStrategy.FAIL_FAST,
                            fallback_agents=[],
                            health_checks=[],
                            version="1.0.0",
                            capabilities=["dummy_processing"],
                            resource_requirements={},
                            compatibility={},
                            # Additional required parameters
                            agent_id="dummy_agent",
                            module_path="OSSS.ai.agents.dummy.EqualityFallbackAgent",
                            discovery_strategy=None,
                            file_path=None,
                            checksum=None,
                            load_count=0,
                            last_loaded=None,
                            is_loaded=False,
                            load_errors=[],
                        )

                agent_class = EqualityFallbackAgent

        if agent_class is None:
            raise ValueError("Unable to determine agent class for metadata creation")

        return cls(
            name=name,
            agent_class=agent_class,
            description=description,
            cognitive_speed="adaptive",
            cognitive_depth="variable",
            processing_pattern="atomic",
            execution_pattern="processor",
            primary_capability="general_processing",
            secondary_capabilities=[],
            pipeline_role="standalone",
            bounded_context="reflection",
            requires_llm=False,
            constructor_pattern=AgentConstructorPattern.FLEXIBLE,
            dependencies=[],
            is_critical=True,
            failure_strategy=FailurePropagationStrategy.FAIL_FAST,
            fallback_agents=[],
            health_checks=[],
            version="1.0.0",
            capabilities=["general_processing"],
            resource_requirements={},
            compatibility={},
            agent_id=None,
            module_path=None,
            discovered_at=time.time(),
            discovery_strategy=None,
            file_path=None,
            checksum=None,
            load_count=0,
            last_loaded=None,
            is_loaded=False,
            load_errors=[],
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMetadata":
        """Create AgentMetadata from dictionary representation."""
        # Handle agent_class reconstruction (simplified for now)
        data.get("agent_class", "")
        import importlib

        try:
            base_agent_module = importlib.import_module("OSSS.ai.agents.base_agent")
            agent_class = base_agent_module.BaseAgent  # Placeholder
        except ImportError:
            # Create a simple dummy class as fallback
            class DeserializationFallbackAgent:
                """Fallback agent class for deserialization when BaseAgent cannot be imported."""

                def __init__(self) -> None:
                    self.name = "dummy_agent"

                async def invoke(
                    self, state: Any, config: Optional[Dict[str, Any]] = None
                ) -> Any:
                    """Dummy invoke method with proper BaseAgent signature."""
                    del config  # Mark as used
                    return state

            agent_class = DeserializationFallbackAgent

        # Handle enum reconstruction
        discovery_strategy = None
        if data.get("discovery_strategy"):
            discovery_strategy = DiscoveryStrategy(data["discovery_strategy"])

        failure_strategy = FailurePropagationStrategy.FAIL_FAST
        if data.get("failure_strategy"):
            failure_strategy = FailurePropagationStrategy(data["failure_strategy"])

        # Ensure type safety for literal values with proper casting
        cognitive_speed_raw = data.get("cognitive_speed", "adaptive")
        cognitive_depth_raw = data.get("cognitive_depth", "variable")
        processing_pattern_raw = data.get("processing_pattern", "atomic")
        execution_pattern_raw = data.get("execution_pattern", "processor")
        pipeline_role_raw = data.get("pipeline_role", "standalone")
        bounded_context_raw = data.get("bounded_context", "reflection")

        cognitive_speed_val: Literal["fast", "slow", "adaptive"] = (
            cast(Literal["fast", "slow", "adaptive"], cognitive_speed_raw)
            if cognitive_speed_raw in ["fast", "slow", "adaptive"]
            else "adaptive"
        )

        cognitive_depth_val: Literal["shallow", "deep", "variable"] = (
            cast(Literal["shallow", "deep", "variable"], cognitive_depth_raw)
            if cognitive_depth_raw in ["shallow", "deep", "variable"]
            else "variable"
        )

        processing_pattern_val: Literal["atomic", "composite", "chain"] = (
            cast(Literal["atomic", "composite", "chain"], processing_pattern_raw)
            if processing_pattern_raw in ["atomic", "composite", "chain"]
            else "atomic"
        )

        execution_pattern_val: Literal[
            "processor", "decision", "aggregator", "validator", "terminator"
        ] = (
            cast(
                Literal[
                    "processor", "decision", "aggregator", "validator", "terminator"
                ],
                execution_pattern_raw,
            )
            if execution_pattern_raw
            in ["processor", "decision", "aggregator", "validator", "terminator"]
            else "processor"
        )

        pipeline_role_val: Literal[
            "entry", "intermediate", "terminal", "standalone"
        ] = (
            cast(
                Literal["entry", "intermediate", "terminal", "standalone"],
                pipeline_role_raw,
            )
            if pipeline_role_raw in ["entry", "intermediate", "terminal", "standalone"]
            else "standalone"
        )

        bounded_context_val: str = "reflection"
        if bounded_context_raw in ["reflection", "transformation", "retrieval"]:
            bounded_context_val = bounded_context_raw

        return cls(
            name=data["name"],
            agent_class=agent_class,
            description=data.get("description", ""),
            cognitive_speed=cognitive_speed_val,
            cognitive_depth=cognitive_depth_val,
            processing_pattern=processing_pattern_val,
            execution_pattern=execution_pattern_val,
            primary_capability=data.get("primary_capability", ""),
            secondary_capabilities=data.get("secondary_capabilities", []),
            pipeline_role=pipeline_role_val,
            bounded_context=bounded_context_val,
            requires_llm=data.get("requires_llm", False),
            constructor_pattern=AgentConstructorPattern.FLEXIBLE,
            dependencies=data.get("dependencies", []),
            is_critical=data.get("is_critical", True),
            failure_strategy=failure_strategy,
            fallback_agents=data.get("fallback_agents", []),
            health_checks=data.get("health_checks", []),
            version=data.get("version", "1.0.0"),
            capabilities=data.get("capabilities", []),
            resource_requirements=data.get("resource_requirements", {}),
            compatibility=data.get("compatibility", {}),
            agent_id=data.get("agent_id"),
            module_path=data.get("module_path"),
            discovered_at=data.get("discovered_at", time.time()),
            discovery_strategy=discovery_strategy,
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            checksum=data.get("checksum"),
            load_count=data.get("load_count", 0),
            last_loaded=data.get("last_loaded"),
            is_loaded=data.get("is_loaded", False),
            load_errors=data.get("load_errors", []),
        )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,  # Required for Type[Any] field
    )


# Try to import BaseAgent and rebuild model to resolve forward references
try:
    from OSSS.ai.agents.base_agent import BaseAgent

    AgentMetadata.model_rebuild()
except (ImportError, Exception):
    # If import fails or model rebuild fails, continue silently
    pass


class TaskClassification(BaseModel):
    """
    Classification of work being performed for semantic event routing.

    This accepts the raw classifier payload from agent_output_meta["_classifier"]
    and derives a concrete `task_type` for NodeExecutionContext / DecisionNode.

    Expected upstream payload keys (all optional except task_type when provided):
    - intent: high-level label, e.g. "action", "question", "query"
    - confidence: overall intent confidence
    - domain, domain_confidence
    - topic, topic_confidence, topics
    - sub_intent, sub_intent_confidence
    - labels, raw
    - model_version
    - original_text, normalized_text, query_terms
    """

    # What DecisionNode / router really care about:
    task_type: Literal[
        "transform",  # Data/format transformation
        "evaluate",   # Critical analysis and assessment
        "retrieve",   # Information and context retrieval
        "synthesize", # Multi-perspective integration
        "summarize",  # Content condensation
        "format",     # Output formatting and structuring
        "filter",     # Content filtering and selection
        "rank",       # Prioritization and ordering
        "compare",    # Comparative analysis
        "explain",    # Explanatory and educational content
        "clarify",    # Intent clarification and refinement
    ] = Field(
        ...,
        description="Type of task being performed",
        json_schema_extra={"example": "evaluate"},
    )

    # High-level intent label from the classifier, e.g. "action", "question"
    intent: Optional[str] = Field(
        None,
        description="Classifier intent label (e.g., 'action', 'question', 'query')",
        max_length=100,
        json_schema_extra={"example": "action"},
    )

    # Overall classifier confidence
    confidence: Optional[float] = Field(
        None,
        description="Overall confidence for the primary intent label (0-1)",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.98},
    )

    # Domain and domain-specific confidence
    domain: Optional[str] = Field(
        None,
        description="Domain of the task (e.g., data_systems, economics, code, policy)",
        max_length=100,
        json_schema_extra={"example": "data_systems"},
    )
    domain_confidence: Optional[float] = Field(
        None,
        description="Confidence for the domain classification (0-1)",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.27},
    )

    # Topic axis
    topic: Optional[str] = Field(
        None,
        description="Primary topic label from classifier",
        max_length=200,
        json_schema_extra={"example": "policies"},
    )
    topic_confidence: Optional[float] = Field(
        None,
        description="Confidence for the primary topic label (0-1)",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.04},
    )
    topics: List[str] = Field(
        default_factory=list,
        description="List of topic labels from classifier",
        json_schema_extra={"example": ["policies"]},
    )

    # More granular intent axis
    sub_intent: Optional[str] = Field(
        None,
        description="More specific subtype of the intent, if available",
        max_length=200,
        json_schema_extra={"example": "create-record"},
    )
    sub_intent_confidence: Optional[float] = Field(
        None,
        description="Confidence for the sub-intent label (0-1)",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.8},
    )

    # Additional classifier metadata
    labels: Optional[Any] = Field(
        None,
        description="Optional raw labels structure from classifier (if any)",
    )
    raw: Optional[Any] = Field(
        None,
        description="Raw classifier payload or backend-specific metadata",
    )
    model_version: Optional[str] = Field(
        None,
        description="Underlying classifier model version",
        max_length=50,
        json_schema_extra={"example": "v1"},
    )

    original_text: Optional[str] = Field(
        None,
        description="Original text that was classified",
        max_length=1000,
        json_schema_extra={"example": "create new consents"},
    )
    normalized_text: Optional[str] = Field(
        None,
        description="Normalized or preprocessed text used by classifier",
        max_length=1000,
        json_schema_extra={"example": "create new consents"},
    )
    query_terms: List[str] = Field(
        default_factory=list,
        description="Tokenized query terms extracted by classifier",
        json_schema_extra={"example": ["create", "new", "consents"]},
    )

    # Local orchestration qualities
    complexity: Literal["simple", "moderate", "complex"] = Field(
        "moderate",
        description="Complexity level of the task",
        json_schema_extra={"example": "moderate"},
    )
    urgency: Literal["low", "normal", "high"] = Field(
        "normal",
        description="Urgency level of the task",
        json_schema_extra={"example": "normal"},
    )

    @model_validator(mode="before")
    @classmethod
    def derive_task_type_from_classifier(cls, data: Any) -> Any:
        """
        Accept raw classifier payloads (like the _classifier block) and
        derive a concrete task_type if it's missing.

        This is what prevents NodeExecutionContext construction from failing
        when only classifier fields are present.
        """
        if not isinstance(data, dict):
            return data

        data = dict(data)

        # Only derive if caller didn't explicitly provide task_type
        if "task_type" not in data:
            raw_intent = data.get("intent")
            intent_lower = str(raw_intent).lower() if raw_intent is not None else ""

            # Map classifier-style intents to TaskClassification.task_type
            intent_to_task_type = {
                "action": "clarify",     # user wants to do something
                "question": "explain",   # Q&A style
                "query": "retrieve",
                "retrieve": "retrieve",
                "search": "retrieve",
                "analyze": "evaluate",
                "evaluate": "evaluate",
            }

            if intent_lower in intent_to_task_type:
                data["task_type"] = intent_to_task_type[intent_lower]
            else:
                # Safe default if we can't map the label
                data["task_type"] = "evaluate"

        return data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation - backward compatibility."""
        return {
            "task_type": self.task_type,
            "intent": self.intent,
            "confidence": self.confidence,
            "domain": self.domain,
            "domain_confidence": self.domain_confidence,
            "topic": self.topic,
            "topic_confidence": self.topic_confidence,
            "topics": self.topics,
            "sub_intent": self.sub_intent,
            "sub_intent_confidence": self.sub_intent_confidence,
            "labels": self.labels,
            "raw": self.raw,
            "model_version": self.model_version,
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "query_terms": self.query_terms,
            "complexity": self.complexity,
            "urgency": self.urgency,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskClassification":
        """Create TaskClassification from dictionary - backward compatibility."""
        complexity_raw = data.get("complexity", "moderate")
        urgency_raw = data.get("urgency", "normal")

        complexity_val: Literal["simple", "moderate", "complex"] = (
            cast(Literal["simple", "moderate", "complex"], complexity_raw)
            if complexity_raw in ["simple", "moderate", "complex"]
            else "moderate"
        )
        urgency_val: Literal["low", "normal", "high"] = (
            cast(Literal["low", "normal", "high"], urgency_raw)
            if urgency_raw in ["low", "normal", "high"]
            else "normal"
        )

        return cls(
            task_type=data["task_type"],
            intent=data.get("intent"),
            confidence=data.get("confidence"),
            domain=data.get("domain"),
            domain_confidence=data.get("domain_confidence"),
            topic=data.get("topic"),
            topic_confidence=data.get("topic_confidence"),
            topics=data.get("topics") or [],
            sub_intent=data.get("sub_intent"),
            sub_intent_confidence=data.get("sub_intent_confidence"),
            labels=data.get("labels"),
            raw=data.get("raw"),
            model_version=data.get("model_version"),
            original_text=data.get("original_text"),
            normalized_text=data.get("normalized_text"),
            query_terms=data.get("query_terms") or [],
            complexity=complexity_val,
            urgency=urgency_val,
        )

    model_config = ConfigDict(
        extra="ignore",          # <-- critical so future classifier fields don't break NodeExecutionContext
        validate_assignment=True
    )

def classify_query_task(query: str) -> TaskClassification:
    """
    Classify a user query into task type and characteristics.

    This is a simplified rule-based implementation. In production,
    this could use LLM-powered classification or ML models.
    """
    query_lower = query.lower()

    task_type: Literal[
        "transform",
        "evaluate",
        "retrieve",
        "synthesize",
        "summarize",
        "format",
        "filter",
        "rank",
        "compare",
        "explain",
        "clarify",
    ]

    query_words = query_lower.split()

    if any(word in query_lower for word in ["translate", "convert", "transform"]):
        task_type = "transform"
    elif any(
        word in query_lower for word in ["analyze", "evaluate", "critique", "assess"]
    ):
        task_type = "evaluate"
    elif any(
        word in query_lower for word in ["combine", "synthesize", "merge", "integrate"]
    ):
        task_type = "synthesize"
    elif any(word in query_words for word in ["find", "search", "retrieve", "lookup"]):
        task_type = "retrieve"
    elif any(word in query_lower for word in ["summarize", "condense", "shorten"]):
        task_type = "summarize"
    elif any(word in query_words for word in ["format", "structure", "organize"]):
        task_type = "format"
    elif any(
        word in query_lower for word in ["explain", "clarify", "help me understand"]
    ):
        task_type = "explain"
    else:
        task_type = "evaluate"

    # Complexity
    complexity: Literal["simple", "moderate", "complex"] = "simple"
    if len(query) > 50:
        complexity = "moderate"
    if len(query) > 200 or any(
        word in query_lower for word in ["complex", "detailed", "comprehensive"]
    ):
        complexity = "complex"

    # Urgency
    urgency: Literal["low", "normal", "high"] = "normal"
    if any(word in query_lower for word in ["urgent", "asap", "quickly", "immediately"]):
        urgency = "high"
    elif any(
        word in query_lower for word in ["when convenient", "no rush", "eventually"]
    ):
        urgency = "low"

    # Domain hints
    domain = None
    domain_keywords = {
        "economics": ["economic", "financial", "market", "trade", "economy"],
        "code": ["code", "programming", "software", "function", "class"],
        "policy": ["policy", "government", "regulation", "law", "legal"],
        "medical": ["medical", "health", "disease", "treatment", "clinical"],
        "science": ["research", "study", "experiment", "hypothesis", "scientific"],
    }

    for domain_name, keywords in domain_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            domain = domain_name
            break

    return TaskClassification(
        task_type=task_type,
        domain=domain,
        # For the rule-based path, you're using the raw query as an "intent-ish" label
        intent=query[:50] + "..." if len(query) > 50 else query,
        # These classifier-metadata fields are unknown for rule-based classification
        confidence=None,  # <-- renamed from intent_confidence
        sub_intent=None,
        sub_intent_confidence=None,
        model_version=None,
        complexity=complexity,
        urgency=urgency,
    )
