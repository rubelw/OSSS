import json
import gzip
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set, cast, Mapping, ClassVar
from copy import deepcopy
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .config.app_config import get_config
from .exceptions import StateTransitionError

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class ContextSnapshot(BaseModel):
    """Immutable snapshot of context state for rollback capabilities."""

    context_id: str = Field(
        description="Context ID this snapshot belongs to", min_length=1
    )
    timestamp: str = Field(description="ISO timestamp when snapshot was created")
    query: str = Field(description="Query at time of snapshot")
    agent_outputs: Dict[str, Any] = Field(
        description="Agent outputs at time of snapshot"
    )
    retrieved_notes: Optional[List[str]] = Field(
        default=None, description="Retrieved notes at time of snapshot"
    )
    user_config: Dict[str, Any] = Field(
        description="User configuration at time of snapshot"
    )
    final_synthesis: Optional[str] = Field(
        default=None, description="Final synthesis at time of snapshot"
    )
    agent_trace: Dict[str, List[Dict[str, Any]]] = Field(
        description="Agent trace at time of snapshot"
    )
    size_bytes: int = Field(
        ge=0, description="Size of context in bytes at time of snapshot"
    )
    compressed: bool = Field(
        default=False, description="Whether snapshot data is compressed"
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_format(cls, v: str) -> str:
        """Validate timestamp is in ISO format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {v}. Must be ISO format.")

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization."""
        return {
            "context_id": self.context_id,
            "timestamp": self.timestamp,
            "query": self.query,
            "agent_outputs": self.agent_outputs,
            "retrieved_notes": self.retrieved_notes,
            "user_config": self.user_config,
            "final_synthesis": self.final_synthesis,
            "agent_trace": self.agent_trace,
            "size_bytes": self.size_bytes,
            "compressed": self.compressed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextSnapshot":
        """Create snapshot from dictionary."""
        return cls(**data)


class ContextCompressionManager:
    """Manages context compression and size optimization."""

    @staticmethod
    def calculate_size(data: Any) -> int:
        """Calculate the approximate size of data in bytes."""
        try:
            size = len(json.dumps(data, default=str).encode("utf-8"))
            logger.debug(f"Calculated size: {size} bytes")
            return size
        except (TypeError, ValueError):
            size = len(str(data).encode("utf-8"))
            logger.debug(f"Fallback size calculation: {size} bytes")
            return size

    @staticmethod
    def compress_data(data: Dict[str, Any]) -> bytes:
        """Compress data using gzip."""
        json_str = json.dumps(data, default=str)
        compressed_data = gzip.compress(json_str.encode("utf-8"))
        logger.debug(f"Compressed data to {len(compressed_data)} bytes")
        return compressed_data

    @staticmethod
    def decompress_data(compressed_data: bytes) -> Dict[str, Any]:
        """Decompress gzipped data."""
        decompressed_data = gzip.decompress(compressed_data).decode("utf-8")
        data = cast(Dict[str, Any], json.loads(decompressed_data))
        logger.debug(f"Decompressed data size: {len(decompressed_data)} bytes")
        return data

    @staticmethod
    def truncate_large_outputs(
        outputs: Dict[str, Any], max_size: int
    ) -> Dict[str, Any]:
        """Truncate large outputs to fit within size limit."""
        truncated = {}
        for key, value in outputs.items():
            if isinstance(value, str) and len(value) > max_size:
                message = f"... [truncated {len(value) - max_size} chars]"
                actual_content_size = max_size - len(message)
                if actual_content_size > 0:
                    truncated[key] = value[:actual_content_size] + message
                else:
                    truncated[key] = f"[truncated {len(value)} chars]"
                logger.debug(f"Truncated value for {key}: {truncated[key]}")
            else:
                truncated[key] = value
        return truncated


class AgentContext(BaseModel):
    """
    Enhanced agent context with size management, compression, snapshot capabilities,
    and LangGraph-compatible features for DAG-based orchestration.

    Features:
    - Agent-isolated mutations to prevent shared global state issues
    - Execution state tracking for failure propagation semantics
    - Reversible state transitions with structured trace metadata
    - Success/failure tracking for conditional execution logic
    """

    OUTPUT_CHAR_CAPS: ClassVar[Dict[str, int]] = {
        "refiner": 4000,
        "critic": 4000,
        "historian": 4000,
        "synthesis": 4000,
    }

    # --- hard per-agent caps (list length) ---
    OUTPUT_LIST_ITEM_CAPS: ClassVar[Dict[str, int]] = {
        "refiner": 100,
        "critic": 100,
        "historian": 100,
        "synthesis": 100,
    }

    OUTPUT_DICT_KEY_CAPS: ClassVar[Dict[str, int]] = {
        "raw": 4000,
        "analysis": 4000,
        "content": 4000,
        "text": 4000,
        "message": 4000,
        "prompt": 4000,
        "system_prompt": 4000,
        "user_prompt": 4000,
    }

    OUTPUT_DICT_TEXT_KEYS: ClassVar[Set[str]] = set(OUTPUT_DICT_KEY_CAPS.keys())

    correlation_id: Optional[str] = None
    execution_id: Optional[str] = None
    thread_id: Optional[str] = None

    query: str = Field(description="The user's query or question to be processed")
    retrieved_notes: Optional[List[str]] = Field(
        default_factory=list, description="Notes retrieved from memory or context"
    )
    agent_outputs: Dict[str, Any] = Field(
        default_factory=dict, description="Output from each agent execution"
    )
    user_config: Dict[str, Any] = Field(
        default_factory=dict, description="User-specific configuration settings"
    )
    final_synthesis: Optional[str] = Field(
        default=None, description="Final synthesized result"
    )
    agent_trace: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict, description="Execution trace for each agent"
    )

    # Context management attributes
    context_id: str = Field(
        default_factory=lambda: hashlib.md5(str(datetime.now()).encode()).hexdigest()[
            :8
        ],
        description="Unique identifier for this context instance",
        min_length=1,
        max_length=50,
    )
    snapshots: List[ContextSnapshot] = Field(
        default_factory=list, description="List of context snapshots for rollback"
    )
    current_size: int = Field(
        default=0, ge=0, description="Current context size in bytes"
    )

    # LangGraph-compatible execution state tracking
    execution_state: Dict[str, Any] = Field(
        default_factory=dict, description="Dynamic execution state data"
    )
    agent_execution_status: Dict[str, str] = Field(
        default_factory=dict,
        description="Agent execution status mapping (pending, running, completed, failed)",
    )
    successful_agents: Set[str] = Field(
        default_factory=set, description="Set of successfully completed agents"
    )
    failed_agents: Set[str] = Field(
        default_factory=set, description="Set of failed agents"
    )
    agent_dependencies: Dict[str, List[str]] = Field(
        default_factory=dict, description="Agent dependency mapping"
    )

    # Execution path tracing for LangGraph DAG edge compatibility
    execution_edges: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of execution edges for DAG tracing"
    )
    conditional_routing: Dict[str, Any] = Field(
        default_factory=dict, description="Conditional routing decisions"
    )
    path_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Execution path metadata"
    )

    # Token usage tracking for LLM resource monitoring
    agent_token_usage: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Token usage tracking per agent: {agent_name: {input_tokens: int, output_tokens: int, total_tokens: int}}",
    )
    total_input_tokens: int = Field(
        default=0, ge=0, description="Total input tokens consumed across all agents"
    )
    total_output_tokens: int = Field(
        default=0, ge=0, description="Total output tokens generated across all agents"
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens (input + output) consumed across all agents",
    )

    # General metadata for API integration and tracing
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="General context metadata"
    )

    # Success tracking for artifact export logic
    success: bool = Field(default=True, description="Overall execution success status")

    # Agent isolation tracking
    agent_mutations: Dict[str, List[str]] = Field(
        default_factory=dict, description="Track which agent modified which fields"
    )
    locked_fields: Set[str] = Field(
        default_factory=set,
        description="Fields that are locked from further modifications",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_agent_output_envelope(self, agent_name: str, envelope: dict) -> None:
        if not isinstance(envelope, dict):
            envelope = {"output": str(envelope)}

        # Ensure stable keys so downstream can rely on them
        envelope.setdefault("agent", agent_name)
        envelope.setdefault("output", "")
        envelope.setdefault("content", envelope.get("output", ""))
        envelope.setdefault("intent", None)
        envelope.setdefault("tone", None)
        envelope.setdefault("action", "read")  # ✅ make action always exist
        envelope.setdefault("sub_tone", None)

        # Store ONLY in execution_state (safe for Pydantic forbid-extra models)
        self.execution_state.setdefault("agent_output_meta", {})
        self.execution_state["agent_output_meta"][agent_name] = envelope

    def get_agent_output_envelope(self, agent_name: str) -> dict:
        return (self.execution_state.get("agent_output_meta") or {}).get(agent_name, {})

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or just whitespace")
        return v.strip()

    @field_validator("agent_execution_status")
    @classmethod
    def validate_agent_status_values(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate that agent execution status values are valid."""
        valid_statuses = {"pending", "running", "completed", "failed"}
        for agent_name, status in v.items():
            if status not in valid_statuses:
                raise ValueError(
                    f"Invalid agent status '{status}' for agent '{agent_name}'. Must be one of: {valid_statuses}"
                )
        return v

    @model_validator(mode="after")
    def validate_agent_sets_consistency(self) -> "AgentContext":
        """Validate that successful and failed agent sets don't overlap."""
        overlap = self.successful_agents & self.failed_agents
        if overlap:
            raise ValueError(f"Agents cannot be both successful and failed: {overlap}")

        # Validate that agent execution status is consistent with success/failure sets
        for agent in self.successful_agents:
            if agent in self.agent_execution_status and self.agent_execution_status[
                agent
            ] not in {"completed"}:
                raise ValueError(
                    f"Agent '{agent}' is in successful_agents but has status '{self.agent_execution_status[agent]}'"
                )

        for agent in self.failed_agents:
            if agent in self.agent_execution_status and self.agent_execution_status[
                agent
            ] not in {"failed"}:
                raise ValueError(
                    f"Agent '{agent}' is in failed_agents but has status '{self.agent_execution_status[agent]}'"
                )

        return self
