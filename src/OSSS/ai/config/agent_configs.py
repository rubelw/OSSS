"""
Agent Configuration Classes for Configurable Prompt Composition

This module provides Pydantic-based configuration classes for dynamic agent behavior
modification. Each agent can be configured via YAML workflows or environment variables
while maintaining full backward compatibility.

Architecture:
- Base configuration classes for common patterns
- Agent-specific configurations with validation
- Integration with existing prompt system
- Environment variable and workflow loading
"""

import os
from typing import (
    Dict,
    List,
    Literal,
    Optional,
    Any,
    Union,
    Type,
    cast,
    overload,
)
from pydantic import BaseModel, Field, ConfigDict


def _default_scoring_criteria() -> List[str]:
    """Default scoring criteria for critic analysis."""
    return ["accuracy", "completeness", "objectivity"]


class PromptConfig(BaseModel):
    """Base configuration for prompt-related settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    custom_system_prompt: Optional[str] = Field(
        None, description="Custom system prompt to override default"
    )
    custom_templates: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom template overrides for specific prompt types",
    )
    template_variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional variables for template substitution",
    )


class BehavioralConfig(BaseModel):
    """Base configuration for agent behavioral patterns."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    custom_constraints: List[str] = Field(
        default_factory=list,
        description="Additional behavioral constraints or guidelines",
    )
    fallback_mode: Literal["graceful", "strict", "adaptive"] = Field(
        "adaptive", description="How to handle configuration errors or edge cases"
    )


class OutputConfig(BaseModel):
    """Base configuration for output formatting and structure."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    format_preference: Literal["raw", "structured", "markdown"] = Field(
        "structured", description="Preferred output format"
    )
    include_metadata: bool = Field(
        True, description="Whether to include execution metadata in output"
    )
    confidence_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for output quality",
    )


class AgentExecutionConfig(BaseModel):
    """Base configuration for execution behavior."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    timeout_seconds: int = Field(
        60, ge=1, le=300, description="Maximum execution time in seconds"
    )
    max_retries: int = Field(
        3, ge=0, le=10, description="Maximum retry attempts on failure"
    )
    enable_caching: bool = Field(True, description="Whether to enable response caching")


# ---------------------------------------------------------------------------
# Agent-Specific Configuration Classes
# ---------------------------------------------------------------------------


class RefinerConfig(BaseModel):
    """Configuration for RefinerAgent behavior and prompt composition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Behavioral settings
    refinement_level: Literal["minimal", "standard", "detailed", "comprehensive"] = (
        Field("standard", description="Level of query refinement detail")
    )
    behavioral_mode: Literal["active", "passive", "adaptive"] = Field(
        "adaptive", description="Agent interaction style"
    )
    output_format: Literal["raw", "prefixed", "structured"] = Field(
        "structured", description="Format for refined query output"
    )

    # Nested configurations
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    behavioral_config: BehavioralConfig = Field(default_factory=BehavioralConfig)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    execution_config: AgentExecutionConfig = Field(default_factory=AgentExecutionConfig)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "RefinerConfig":
        """Create RefinerConfig from dictionary (workflow integration)."""
        return cls(**config)

    @classmethod
    def from_env(cls, prefix: str = "REFINER") -> "RefinerConfig":
        """Create RefinerConfig from environment variables."""
        config: Dict[str, Any] = {}

        # Load simple settings
        if env_val := os.getenv(f"{prefix}_REFINEMENT_LEVEL"):
            config["refinement_level"] = env_val
        if env_val := os.getenv(f"{prefix}_BEHAVIORAL_MODE"):
            config["behavioral_mode"] = env_val
        if env_val := os.getenv(f"{prefix}_OUTPUT_FORMAT"):
            config["output_format"] = env_val

        return cls(**config)

    def to_prompt_config(self) -> Dict[str, Any]:
        """Convert to format compatible with existing prompt system."""
        return {
            "refinement_level": self.refinement_level,
            "behavioral_mode": self.behavioral_mode,
            "output_format": self.output_format,
            "custom_constraints": self.behavioral_config.custom_constraints,
            "template_variables": self.prompt_config.template_variables,
        }


class CriticConfig(BaseModel):
    """Configuration for CriticAgent behavior and prompt composition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Behavioral settings
    analysis_depth: Literal["shallow", "medium", "deep", "comprehensive"] = Field(
        "medium", description="Depth of critical analysis"
    )
    confidence_reporting: bool = Field(
        True, description="Whether to include confidence scores in analysis"
    )
    bias_detection: bool = Field(
        True, description="Whether to actively detect and report biases"
    )
    scoring_criteria: List[str] = Field(
        default_factory=_default_scoring_criteria,
        description="Criteria for evaluating content quality",
    )

    # Nested configurations
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    behavioral_config: BehavioralConfig = Field(default_factory=BehavioralConfig)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    execution_config: AgentExecutionConfig = Field(
        default_factory=lambda: AgentExecutionConfig(timeout_seconds=120)
    )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "CriticConfig":
        """Create CriticConfig from dictionary (workflow integration)."""
        return cls(**config)

    @classmethod
    def from_env(cls, prefix: str = "CRITIC") -> "CriticConfig":
        """Create CriticConfig from environment variables."""
        config: Dict[str, Any] = {}

        if env_val := os.getenv(f"{prefix}_ANALYSIS_DEPTH"):
            config["analysis_depth"] = env_val
        if env_val := os.getenv(f"{prefix}_CONFIDENCE_REPORTING"):
            config["confidence_reporting"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_BIAS_DETECTION"):
            config["bias_detection"] = env_val.lower() == "true"

        return cls(**config)

    def to_prompt_config(self) -> Dict[str, Any]:
        """Convert to format compatible with existing prompt system."""
        return {
            "analysis_depth": self.analysis_depth,
            "confidence_reporting": str(self.confidence_reporting),
            "bias_detection": str(self.bias_detection),
            "scoring_criteria": self.scoring_criteria,
            "custom_constraints": self.behavioral_config.custom_constraints,
        }


class HistorianConfig(BaseModel):
    """Configuration for HistorianAgent behavior and prompt composition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Behavioral settings
    search_depth: Literal["shallow", "standard", "deep", "exhaustive"] = Field(
        "standard", description="Depth of context search and retrieval"
    )
    relevance_threshold: float = Field(
        0.6, ge=0.0, le=1.0, description="Minimum relevance score for including context"
    )
    context_expansion: bool = Field(
        True, description="Whether to expand context with related information"
    )
    memory_scope: Literal["session", "recent", "full", "selective"] = Field(
        "recent", description="Scope of memory to search and analyze"
    )

    # Hybrid search configuration
    hybrid_search_enabled: bool = Field(
        False, description="Whether to enable hybrid file + database search"
    )
    hybrid_search_file_ratio: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        description="Ratio of search results from files vs database (0.0-1.0)",
    )
    database_relevance_boost: float = Field(
        0.0,
        ge=-0.5,
        le=0.5,
        description="Relevance score boost for database results (-0.5 to +0.5)",
    )
    search_timeout_seconds: int = Field(
        5, ge=1, le=30, description="Database search timeout in seconds"
    )
    deduplication_threshold: float = Field(
        0.8,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for result deduplication (0.0-1.0)",
    )
    minimum_results_threshold: int = Field(
        3,
        ge=1,
        le=10,
        description="Minimum number of results to keep when LLM filters all results",
    )

    # Nested configurations
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    behavioral_config: BehavioralConfig = Field(default_factory=BehavioralConfig)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    execution_config: AgentExecutionConfig = Field(
        default_factory=lambda: AgentExecutionConfig(timeout_seconds=90)
    )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "HistorianConfig":
        """Create HistorianConfig from dictionary (workflow integration)."""
        return cls(**config)

    @classmethod
    def from_env(cls, prefix: str = "HISTORIAN") -> "HistorianConfig":
        """Create HistorianConfig from environment variables."""
        config: Dict[str, Any] = {}

        if env_val := os.getenv(f"{prefix}_SEARCH_DEPTH"):
            config["search_depth"] = env_val
        if env_val := os.getenv(f"{prefix}_RELEVANCE_THRESHOLD"):
            config["relevance_threshold"] = float(env_val)
        if env_val := os.getenv(f"{prefix}_CONTEXT_EXPANSION"):
            config["context_expansion"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_MEMORY_SCOPE"):
            config["memory_scope"] = env_val

        # Hybrid search environment variables
        if env_val := os.getenv(f"{prefix}_HYBRID_SEARCH_ENABLED"):
            config["hybrid_search_enabled"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_HYBRID_SEARCH_FILE_RATIO"):
            config["hybrid_search_file_ratio"] = float(env_val)
        if env_val := os.getenv(f"{prefix}_DATABASE_RELEVANCE_BOOST"):
            config["database_relevance_boost"] = float(env_val)
        if env_val := os.getenv(f"{prefix}_SEARCH_TIMEOUT_SECONDS"):
            config["search_timeout_seconds"] = int(env_val)
        if env_val := os.getenv(f"{prefix}_DEDUPLICATION_THRESHOLD"):
            config["deduplication_threshold"] = float(env_val)
        if env_val := os.getenv(f"{prefix}_MINIMUM_RESULTS_THRESHOLD"):
            config["minimum_results_threshold"] = int(env_val)

        return cls(**config)

    def to_prompt_config(self) -> Dict[str, Any]:
        """Convert to format compatible with existing prompt system."""
        return {
            "search_depth": self.search_depth,
            "relevance_threshold": str(self.relevance_threshold),
            "context_expansion": str(self.context_expansion),
            "memory_scope": self.memory_scope,
            "hybrid_search_enabled": str(self.hybrid_search_enabled),
            "hybrid_search_file_ratio": str(self.hybrid_search_file_ratio),
            "database_relevance_boost": str(self.database_relevance_boost),
            "search_timeout_seconds": str(self.search_timeout_seconds),
            "deduplication_threshold": str(self.deduplication_threshold),
            "minimum_results_threshold": str(self.minimum_results_threshold),
            "custom_constraints": self.behavioral_config.custom_constraints,
        }


class SynthesisConfig(BaseModel):
    """Configuration for SynthesisAgent behavior and prompt composition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Behavioral settings
    synthesis_strategy: Literal["comprehensive", "focused", "balanced", "creative"] = (
        Field(
            "balanced", description="Strategy for synthesizing multiple agent outputs"
        )
    )
    thematic_focus: Optional[str] = Field(
        None, description="Optional thematic focus for synthesis"
    )
    meta_analysis: bool = Field(
        True, description="Whether to include meta-analysis of the synthesis process"
    )
    integration_mode: Literal["sequential", "parallel", "hierarchical", "adaptive"] = (
        Field("adaptive", description="How to integrate different agent perspectives")
    )

    # Nested configurations
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    behavioral_config: BehavioralConfig = Field(default_factory=BehavioralConfig)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    execution_config: AgentExecutionConfig = Field(
        default_factory=lambda: AgentExecutionConfig(timeout_seconds=300)
    )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "SynthesisConfig":
        """Create SynthesisConfig from dictionary (workflow integration)."""
        return cls(**config)

    @classmethod
    def from_env(cls, prefix: str = "SYNTHESIS") -> "SynthesisConfig":
        """Create SynthesisConfig from environment variables."""
        config: Dict[str, Any] = {}

        if env_val := os.getenv(f"{prefix}_SYNTHESIS_STRATEGY"):
            config["synthesis_strategy"] = env_val
        if env_val := os.getenv(f"{prefix}_THEMATIC_FOCUS"):
            config["thematic_focus"] = env_val
        if env_val := os.getenv(f"{prefix}_META_ANALYSIS"):
            config["meta_analysis"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_INTEGRATION_MODE"):
            config["integration_mode"] = env_val

        return cls(**config)

    def to_prompt_config(self) -> Dict[str, Any]:
        """Convert to format compatible with existing prompt system."""
        return {
            "synthesis_strategy": self.synthesis_strategy,
            "thematic_focus": self.thematic_focus or "",
            "meta_analysis": str(self.meta_analysis),
            "integration_mode": self.integration_mode,
            "custom_constraints": self.behavioral_config.custom_constraints,
        }


class FinalConfig(BaseModel):
    """
    Configuration for FinalAgent behavior and prompt composition.

    This aligns with FinalAgent's responsibilities:
    - Build the final user-facing answer
    - Integrate RAG context when present
    - Enforce strict role-identity guardrails
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Behavioral settings
    answer_style: Literal["concise", "balanced", "detailed"] = Field(
        "balanced",
        description="Preferred style for final answers (length and depth).",
    )
    include_refiner_context: bool = Field(
        True,
        description="Whether to include refiner output in the FINAL prompt for extra context.",
    )
    enforce_role_identity_guardrails: bool = Field(
        True,
        description="If true, strictly avoid hallucinating real-person role identities.",
    )
    rag_required_for_role_identity: bool = Field(
        True,
        description=(
            "If true, FINAL must refuse to name real-world role holders "
            "unless RAG context explicitly provides the identity."
        ),
    )
    fallback_no_context_message: str = Field(
        "No relevant context found for this query. Please verify the query or try again.",
        description="Message to use when no RAG context is available.",
    )

    # Nested configurations
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    behavioral_config: BehavioralConfig = Field(default_factory=BehavioralConfig)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    execution_config: AgentExecutionConfig = Field(
        default_factory=lambda: AgentExecutionConfig(timeout_seconds=120)
    )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "FinalConfig":
        """Create FinalConfig from dictionary (workflow integration)."""
        return cls(**config)

    @classmethod
    def from_env(cls, prefix: str = "FINAL") -> "FinalConfig":
        """Create FinalConfig from environment variables."""
        config: Dict[str, Any] = {}

        if env_val := os.getenv(f"{prefix}_ANSWER_STYLE"):
            config["answer_style"] = env_val
        if env_val := os.getenv(f"{prefix}_INCLUDE_REFINER_CONTEXT"):
            config["include_refiner_context"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_ENFORCE_ROLE_IDENTITY_GUARDRAILS"):
            config["enforce_role_identity_guardrails"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_RAG_REQUIRED_FOR_ROLE_IDENTITY"):
            config["rag_required_for_role_identity"] = env_val.lower() == "true"
        if env_val := os.getenv(f"{prefix}_FALLBACK_NO_CONTEXT_MESSAGE"):
            config["fallback_no_context_message"] = env_val

        return cls(**config)

    def to_prompt_config(self) -> Dict[str, Any]:
        """
        Convert to a flat dict compatible with the existing prompt system.

        FinalAgent can read these from ctx.execution_state["execution_config"] or
        a similar structure.
        """
        return {
            "answer_style": self.answer_style,
            "include_refiner_context": str(self.include_refiner_context),
            "enforce_role_identity_guardrails": str(
                self.enforce_role_identity_guardrails
            ),
            "rag_required_for_role_identity": str(self.rag_required_for_role_identity),
            "fallback_no_context_message": self.fallback_no_context_message,
            "format_preference": self.output_config.format_preference,
            "custom_constraints": self.behavioral_config.custom_constraints,
            "template_variables": self.prompt_config.template_variables,
        }


# ---------------------------------------------------------------------------
# Configuration Union Type for Factory Patterns
# ---------------------------------------------------------------------------

AgentConfigType = Union[
    RefinerConfig,
    CriticConfig,
    HistorianConfig,
    SynthesisConfig,
    FinalConfig,
]


# ---------------------------------------------------------------------------
# Overloads for better type safety
# ---------------------------------------------------------------------------

@overload
def get_agent_config_class(agent_type: Literal["refiner"]) -> Type[RefinerConfig]: ...


@overload
def get_agent_config_class(agent_type: Literal["critic"]) -> Type[CriticConfig]: ...


@overload
def get_agent_config_class(
    agent_type: Literal["historian"],
) -> Type[HistorianConfig]: ...


@overload
def get_agent_config_class(
    agent_type: Literal["synthesis"],
) -> Type[SynthesisConfig]: ...


@overload
def get_agent_config_class(
    agent_type: Literal["final"],
) -> Type[FinalConfig]: ...


@overload
def get_agent_config_class(agent_type: str) -> Type[AgentConfigType]: ...


def get_agent_config_class(agent_type: str) -> Type[AgentConfigType]:
    """Get the appropriate configuration class for an agent type."""
    config_mapping = {
        "refiner": RefinerConfig,
        "critic": CriticConfig,
        "historian": HistorianConfig,
        "synthesis": SynthesisConfig,
        "final": FinalConfig,
    }

    if agent_type not in config_mapping:
        raise ValueError(f"Unknown agent type: {agent_type}")

    return cast(Type[AgentConfigType], config_mapping[agent_type])


# ---------------------------------------------------------------------------
# Overloads for config creation with better type safety
# ---------------------------------------------------------------------------

@overload
def create_agent_config(
    agent_type: Literal["refiner"], config_dict: Dict[str, Any]
) -> RefinerConfig: ...


@overload
def create_agent_config(
    agent_type: Literal["critic"], config_dict: Dict[str, Any]
) -> CriticConfig: ...


@overload
def create_agent_config(
    agent_type: Literal["historian"], config_dict: Dict[str, Any]
) -> HistorianConfig: ...


@overload
def create_agent_config(
    agent_type: Literal["synthesis"], config_dict: Dict[str, Any]
) -> SynthesisConfig: ...


@overload
def create_agent_config(
    agent_type: Literal["final"], config_dict: Dict[str, Any]
) -> FinalConfig: ...


@overload
def create_agent_config(
    agent_type: str, config_dict: Dict[str, Any]
) -> AgentConfigType: ...


def create_agent_config(
    agent_type: str, config_dict: Dict[str, Any]
) -> AgentConfigType:
    """Factory function to create appropriate agent configuration from dictionary."""
    config_class = get_agent_config_class(agent_type)
    return config_class.from_dict(config_dict)
