import logging
import json
import gzip
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set, cast, Mapping, ClassVar
from copy import deepcopy
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .config.app_config import get_config
from .exceptions import StateTransitionError

logger = logging.getLogger(__name__)

class AgentExecutionInfo(BaseModel):
    """
    Per-agent execution record used by BaseAgent.run_with_retry()
    to avoid double-completion + to determine real success.
    """
    agent: str
    success: Optional[bool] = None   # None = not recorded
    completed: bool = False
    status: str = "pending"          # pending/running/completed/failed

    step_id: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None

    error_type: Optional[str] = None
    error_message: Optional[str] = None

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
            return len(json.dumps(data, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            return len(str(data).encode("utf-8"))

    @staticmethod
    def compress_data(data: Dict[str, Any]) -> bytes:
        """Compress data using gzip."""
        json_str = json.dumps(data, default=str)
        return gzip.compress(json_str.encode("utf-8"))

    @staticmethod
    def decompress_data(compressed_data: bytes) -> Dict[str, Any]:
        """Decompress gzipped data."""
        json_str = gzip.decompress(compressed_data).decode("utf-8")
        return cast(Dict[str, Any], json.loads(json_str))

    @staticmethod
    def truncate_large_outputs(
        outputs: Dict[str, Any], max_size: int
    ) -> Dict[str, Any]:
        """Truncate large outputs to fit within size limit."""
        truncated = {}
        for key, value in outputs.items():
            if isinstance(value, str) and len(value) > max_size:
                # Calculate actual truncated size to account for the message
                message = f"... [truncated {len(value) - max_size} chars]"
                actual_content_size = max_size - len(message)
                if actual_content_size > 0:
                    truncated[key] = value[:actual_content_size] + message
                else:
                    # If max_size is too small, just show the truncation message
                    truncated[key] = f"[truncated {len(value)} chars]"
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
        "final": 4000
    }

    # --- hard per-agent caps (list length) ---
    OUTPUT_LIST_ITEM_CAPS: ClassVar[Dict[str, int]] = {
        "refiner": 100,
        "critic": 100,
        "historian": 100,
        "synthesis": 100,
        "final": 100,
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

    task_classification: Optional[Dict[str, Any]] = None
    cognitive_classification: Optional[Dict[str, Any]] = None

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
    agent_executions: dict[str, dict] = Field(default_factory=dict)

    # 🔹 NEW: orchestration / logging metadata
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Non-user-facing execution metadata (per-agent envelopes, traces, etc.)",
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

    completed: bool = False

    # Agent isolation tracking
    agent_mutations: Dict[str, List[str]] = Field(
        default_factory=dict, description="Track which agent modified which fields"
    )
    locked_fields: Set[str] = Field(
        default_factory=set,
        description="Fields that are locked from further modifications",
    )

    final: Optional[str] = None  # <-- add this

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # Internal helpers for execution_metadata.agent_outputs
    # ------------------------------------------------------------------
    def _ensure_agent_outputs_metadata(self) -> Dict[str, Any]:
        """
        Ensure `execution_metadata["agent_outputs"]` exists and is a dict.
        """
        emd = getattr(self, "execution_metadata", None)

        if not isinstance(emd, dict):
            logger.warning(
                "[AgentContext] execution_metadata was %r; resetting to {}",
                emd,
            )
            emd = {}
            # use object.__setattr__ to bypass any Pydantic magic
            object.__setattr__(self, "execution_metadata", emd)

        agent_outputs_meta = emd.get("agent_outputs")

        if not isinstance(agent_outputs_meta, dict):
            logger.warning(
                "[AgentContext] execution_metadata['agent_outputs'] was %r; resetting to {}",
                agent_outputs_meta,
            )
            agent_outputs_meta = {}
            emd["agent_outputs"] = agent_outputs_meta

        return agent_outputs_meta


    def set_task_classification(self, task_classification: Dict[str, Any]) -> None:
        """Store the task classification result in the context."""
        self.task_classification = task_classification
        self.execution_state["task_classification"] = task_classification

    def get_task_classification(self) -> Dict[str, Any]:
        """Retrieve the task classification from the context."""
        return self.task_classification or {}

    def set_cognitive_classification(self, cognitive_classification: Dict[str, Any]) -> None:
        """Store the cognitive classification result in the context."""
        self.cognitive_classification = cognitive_classification
        self.execution_state["cognitive_classification"] = cognitive_classification

    def get_cognitive_classification(self) -> Dict[str, Any]:
        """Retrieve the cognitive classification from the context."""
        return self.cognitive_classification or {}

    def _canon_agent(self, agent_name: str) -> str:
        return (agent_name or "").strip().lower()

    def add_agent_output_envelope(self, agent_name: str, envelope: dict) -> None:
        agent = self._canon_agent(agent_name)

        if not isinstance(envelope, dict):
            envelope = {"output": str(envelope)}

        # Ensure stable keys so downstream can rely on them
        envelope.setdefault("agent", agent)
        envelope.setdefault("output", "")
        envelope.setdefault("content", envelope.get("output", ""))
        envelope.setdefault("intent", None)
        envelope.setdefault("tone", None)
        envelope.setdefault("action", "read")  # ✅ make action always exist
        envelope.setdefault("sub_tone", None)

        # Store ONLY in execution_state (safe for Pydantic forbid-extra models)
        self.execution_state.setdefault("agent_output_meta", {})
        self.execution_state["agent_output_meta"][agent] = envelope

        # 🔹 ALSO store in execution_metadata.agent_outputs with safety + logging
        meta_outputs = self._ensure_agent_outputs_metadata()
        meta_outputs[agent] = envelope

        logger.debug(
            "[AgentContext] stored agent output envelope",
            extra={"agent": agent, "keys": list(envelope.keys())},
        )

    def get_agent_output_envelope(self, agent_name: str) -> dict:
        agent = self._canon_agent(agent_name)
        return (self.execution_state.get("agent_output_meta") or {}).get(agent, {})

    # ------------------------------------------------------------------
    # NEW: classifier + user-question helpers backed by execution_state
    # ------------------------------------------------------------------

    def set_classifier_result(self, result: Dict[str, Any]) -> None:
        """
        Store a normalized classifier result dict so other agents can reuse it.
        This now also sets task_classification and cognitive_classification.
        """
        exec_state = self.execution_state or {}
        if not isinstance(exec_state, dict):
            exec_state = {}

        # Store the classifier result
        exec_state["classifier_result"] = result or {}

        # Extract and store task_classification and cognitive_classification
        task_classification = result.get("task_classification", {})
        cognitive_classification = result.get("cognitive_classification", {})

        # Store them in the execution state and update the context
        self.set_task_classification(task_classification)
        self.set_cognitive_classification(cognitive_classification)

        self.execution_state = exec_state

    def get_classifier_result(self) -> Dict[str, Any]:
        """
        Retrieve the classifier result dict. Always returns a dict (possibly empty).
        """
        exec_state = self.execution_state or {}
        if not isinstance(exec_state, dict):
            return {}
        result = exec_state.get("classifier_result") or {}
        return result if isinstance(result, dict) else {}

    def set_user_question(self, text: str) -> None:
        """
        Store the original user question / query for reuse by downstream agents.
        """
        exec_state = self.execution_state or {}
        if not isinstance(exec_state, dict):
            exec_state = {}
        exec_state["user_question"] = text or ""
        self.execution_state = exec_state

    def get_user_question(self) -> str:
        """
        Retrieve the stored user question. Falls back to empty string if missing.
        """
        exec_state = self.execution_state or {}
        if not isinstance(exec_state, dict):
            return ""
        return (exec_state.get("user_question") or "").strip()

    def get_last_output(self, agent_name: str) -> Optional[Any]:
        """
        Convenience helper so agents can ask: 'what did X output most recently?'
        """
        agent = self._canon_agent(agent_name)
        return self.agent_outputs.get(agent)

    # ------------------------------------------------------------------

    def get_agent_execution(self, agent_name: str) -> Optional[AgentExecutionInfo]:
        agent = self._canon_agent(agent_name)
        return self.agent_executions.get(agent)

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or just whitespace")
        return v.strip()

    from pydantic import field_validator

    @field_validator("agent_execution_status", check_fields=False)
    @classmethod
    def validate_agent_status_values(cls, v: Dict[str, str]) -> Dict[str, str]:
        valid_statuses = {"pending", "running", "completed", "failed"}
        for agent_name, status in v.items():
            if status not in valid_statuses:
                raise ValueError(
                    f"Invalid agent status '{status}' for agent '{agent_name}'. "
                    f"Must be one of: {valid_statuses}"
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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Store compression manager as private attribute for mypy compatibility
        self._compression_manager = ContextCompressionManager()
        self._update_size()

    @property
    def compression_manager(self) -> ContextCompressionManager:
        """Get the compression manager instance."""
        return self._compression_manager

    def _cap_agent_output(self, agent_name: str, output: Any) -> Any:
        """
        Apply hard caps to agent outputs to prevent context bloat.

        Rules:
        - str → cap by agent char cap
        - list[str] → cap list length + cap each item
        - dict → cap selected text keys (per-key caps win)
        - recurse one level only (safe + cheap)
        """
        agent = self._canon_agent(agent_name)


        char_cap = self.OUTPUT_CHAR_CAPS.get(agent)
        list_cap = self.OUTPUT_LIST_ITEM_CAPS.get(agent)

        if not char_cap and not list_cap:
            return output

        def cap_str(s: str, cap: int) -> str:
            return s if len(s) <= cap else s[:cap]

        # --- string output ---
        if isinstance(output, str) and char_cap:
            return cap_str(output, char_cap)

        # --- list output ---
        if isinstance(output, list):
            capped_list = output

            # 1) cap list length first (BIG WIN)
            if list_cap:
                capped_list = capped_list[:list_cap]

            # 2) cap list[str] items
            if char_cap and all(isinstance(x, str) for x in capped_list):
                capped_list = [cap_str(x, char_cap) for x in capped_list]

            return capped_list

        # --- dict output ---
        if isinstance(output, dict):
            capped = dict(output)

            # 1) cap known text keys
            for key, key_cap in self.OUTPUT_DICT_KEY_CAPS.items():
                val = capped.get(key)

                if isinstance(val, str):
                    capped[key] = cap_str(val, key_cap)

                elif isinstance(val, list):
                    # cap list length
                    if list_cap:
                        val = val[:list_cap]

                    # cap list[str] items
                    if all(isinstance(x, str) for x in val):
                        capped[key] = [cap_str(x, key_cap) for x in val]
                    else:
                        capped[key] = val

            # 2) shallow recursion (one level only)
            for k, v in list(capped.items()):
                if isinstance(v, dict):
                    nested = dict(v)
                    for nk, nk_cap in self.OUTPUT_DICT_KEY_CAPS.items():
                        nv = nested.get(nk)

                        if isinstance(nv, str):
                            nested[nk] = cap_str(nv, nk_cap)

                        elif isinstance(nv, list):
                            if list_cap:
                                nv = nv[:list_cap]
                            if all(isinstance(x, str) for x in nv):
                                nested[nk] = [cap_str(x, nk_cap) for x in nv]
                            else:
                                nested[nk] = nv

                    capped[k] = nested

            return capped

        return output

    def get_context_id(self) -> str:
        """Get the unique context identifier."""
        return self.context_id

    def get_current_size_bytes(self) -> int:
        """Get the current context size in bytes."""
        return self.current_size

    def _update_size(self) -> None:
        """Update the current context size calculation."""
        data = {
            "query": self.query,
            "agent_outputs": self.agent_outputs,
            "retrieved_notes": self.retrieved_notes,
            "user_config": self.user_config,
            "final_synthesis": self.final_synthesis,
            "agent_trace": self.agent_trace,
        }
        self.current_size = self.compression_manager.calculate_size(data)

    def _check_size_limits(self) -> None:
        """Check if context exceeds size limits and apply compression if needed."""
        config = get_config()
        max_size = getattr(
            config.testing, "max_context_size_bytes", 1024 * 1024
        )  # 1MB default

        if self.current_size > max_size:
            logger.warning(
                f"Context size ({self.current_size} bytes) exceeds limit ({max_size} bytes), applying compression"
            )
            self._compress_context(max_size)

    def _compress_context(self, target_size: int) -> None:
        """Compress context to fit within target size."""
        # First, try truncating large outputs
        max_output_size = target_size // max(len(self.agent_outputs), 1)
        self.agent_outputs = self.compression_manager.truncate_large_outputs(
            self.agent_outputs, max_output_size
        )

        # Update size after truncation
        self._update_size()

        # If still too large, compress agent trace
        if self.current_size > target_size:
            # Keep only the most recent trace entries
            for agent_name in self.agent_trace:
                if len(self.agent_trace[agent_name]) > 3:
                    self.agent_trace[agent_name] = self.agent_trace[agent_name][-3:]

            self._update_size()
            logger.info(f"Context compressed to {self.current_size} bytes")

    def _clip(s: str, n: int = 4000) -> str:
        s = s or ""
        return s if len(s) <= n else s[:n] + "…[truncated]"

    def add_agent_output(self, agent_name: str, output: Any) -> None:
        """Add agent output with size monitoring."""
        agent = self._canon_agent(agent_name)

        # If the agent already returned an envelope, preserve it.
        if isinstance(output, dict):
            envelope = dict(output)
            content = envelope.get("content") or envelope.get("text") or envelope.get("message") or ""
            meta = envelope.get("meta") or {}
            # Promote common meta keys if they’re top-level
            for k in ("intent", "tone"):
                if k in envelope and k not in meta:
                    meta[k] = envelope[k]
            action = envelope.get("action") if isinstance(envelope, dict) else None
            intent = envelope.get("intent") if isinstance(envelope, dict) else None
            tone = envelope.get("tone") if isinstance(envelope, dict) else None

            wrapped = {"content": content, "meta": meta}
            if action is not None:
                wrapped["action"] = action
            if intent is not None:
                wrapped["intent"] = intent
            if tone is not None:
                wrapped["tone"] = tone

            self.add_agent_output_envelope(agent, wrapped)

            output = content  # what you store in agent_outputs for display
        else:
            # Existing behavior for non-dicts
            output = (
                output.content
                if hasattr(output, "content")
                else (output.text if hasattr(output, "text") else str(output))
            )

        def clip(s: str, n: int = 4000) -> str:
            s = s or ""
            return s if len(s) <= n else s[:n] + "…[truncated]"

        # 0) Normalize to TEXT ONLY (prevents LLMResponse objects leaking into context)
        output = (
            output.content
            if hasattr(output, "content")
            else (output.text if hasattr(output, "text") else str(output))
        )

        # 1) Hard per-agent caps (string-only)
        cap = self.OUTPUT_CHAR_CAPS.get(agent.lower())
        if cap and isinstance(output, str):
            output = output[:cap]

        # 2) Existing cap logic (kept)
        output = self._cap_agent_output(agent, output)

        # 3) Safety clip for prompt hygiene / logging hygiene
        output = clip(output)

        self.agent_outputs[agent] = output
        self._update_size()
        self._check_size_limits()
        logger.info(f"Added output for agent '{agent}': {str(output)[:100]}...")
        logger.debug(
            f"Context size after adding {agent}: {self.current_size} bytes"
        )

        # 🔹 Optionally keep a simple mirror in execution_metadata.agent_outputs
        try:
            meta_outputs = self._ensure_agent_outputs_metadata()
            # Only set a simple mirror if no richer envelope exists:
            meta_outputs.setdefault(agent, {"content": output})
        except Exception as e:
            logger.warning(
                "[AgentContext] failed to update execution_metadata.agent_outputs",
                extra={"agent": agent, "error": str(e)},
            )

        self.agent_outputs[agent] = output


    def add_agent_token_usage(
        self,
        agent_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: Optional[int] = None,
    ) -> None:
        """
        Add token usage information for a specific agent.

        Parameters
        ----------
        agent_name : str
            Name of the agent that consumed tokens
        input_tokens : int, default=0
            Number of input tokens consumed
        output_tokens : int, default=0
            Number of output tokens generated
        total_tokens : Optional[int], default=None
            Total tokens consumed. If None, calculated as input_tokens + output_tokens
        """
        agent = self._canon_agent(agent_name)
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token counts cannot be negative")

        if total_tokens is None:
            total_tokens = input_tokens + output_tokens
        elif total_tokens < 0:
            raise ValueError("Total tokens cannot be negative")

        # Store agent-specific token usage
        self.agent_token_usage[agent] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        # Update total counters
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_tokens += total_tokens

        logger.debug(
            f"Token usage recorded for agent '{agent}': "
            f"input={input_tokens}, output={output_tokens}, total={total_tokens}"
        )

    def get_agent_token_usage(self, agent_name: str) -> Dict[str, int]:
        """
        Get token usage information for a specific agent.

        Parameters
        ----------
        agent_name : str
            Name of the agent

        Returns
        -------
        Dict[str, int]
            Dictionary with keys: input_tokens, output_tokens, total_tokens
            Returns zeros if agent has no recorded token usage
        """
        agent = self._canon_agent(agent_name)

        return self.agent_token_usage.get(
            agent,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
        )

    def get_total_token_usage(self) -> Dict[str, int]:
        """
        Get total token usage across all agents.

        Returns
        -------
        Dict[str, int]
            Dictionary with total input_tokens, output_tokens, and total_tokens
        """
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
        }

    def log_trace(
            self,
            agent_name: str,
            input_data: Any,
            output_data: Any,
            timestamp: Optional[str] = None,
    ) -> None:
        """Log agent trace with size monitoring."""
        agent = self._canon_agent(agent_name)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        trace_entry = {"timestamp": timestamp, "input": input_data, "output": output_data}

        if agent not in self.agent_trace:
            self.agent_trace[agent] = []

        self.agent_trace[agent].append(trace_entry)
        self._update_size()
        self._check_size_limits()
        logger.debug(f"Logged trace for agent '{agent}': {str(trace_entry)[:200]}...")

    def get_output(self, agent_name: str) -> Optional[Any]:
        agent = self._canon_agent(agent_name)

        logger.debug(f"Retrieving output for agent '{agent}'")
        return self.agent_outputs.get(agent)

    def update_user_config(self, config_updates: Dict[str, Any]) -> None:
        """Update the user_config dictionary with new key-value pairs."""
        self.user_config.update(config_updates)
        self._update_size()
        self._check_size_limits()
        logger.info(f"Updated user_config: {self.user_config}")

    def get_user_config(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from user_config with an optional default."""
        return self.user_config.get(key, default)

    def set_final_synthesis(self, summary: str) -> None:
        """Set the final synthesis string."""
        self.final_synthesis = summary
        self._update_size()
        self._check_size_limits()
        logger.info(f"Set final_synthesis: {summary[:100]}...")

    def get_final_synthesis(self) -> Optional[str]:
        """Get the final synthesis string."""
        return self.final_synthesis

    def create_snapshot(self, label: Optional[str] = None) -> str:
        """Create an immutable snapshot of the current context state.

        Parameters
        ----------
        label : str, optional
            Optional label for the snapshot

        Returns
        -------
        str
            Snapshot ID for later restoration
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot_id = f"{timestamp}_{len(self.snapshots)}"

        snapshot = ContextSnapshot(
            context_id=self.context_id,
            timestamp=timestamp,
            query=self.query,
            agent_outputs=deepcopy(self.agent_outputs),
            retrieved_notes=deepcopy(self.retrieved_notes),
            user_config=deepcopy(self.user_config),
            final_synthesis=self.final_synthesis,
            agent_trace=deepcopy(self.agent_trace),
            size_bytes=self.current_size,
        )

        self.snapshots.append(snapshot)
        logger.info(
            f"Created context snapshot {snapshot_id}"
            + (f" with label '{label}'" if label else "")
        )
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore context to a previous snapshot state.

        Parameters
        ----------
        snapshot_id : str
            The snapshot ID to restore

        Returns
        -------
        bool
            True if restoration was successful, False otherwise
        """
        for snapshot in self.snapshots:
            if snapshot.timestamp == snapshot_id.split("_")[0]:
                self.query = snapshot.query
                self.agent_outputs = deepcopy(snapshot.agent_outputs)
                self.retrieved_notes = deepcopy(snapshot.retrieved_notes)
                self.user_config = deepcopy(snapshot.user_config)
                self.final_synthesis = snapshot.final_synthesis
                self.agent_trace = deepcopy(snapshot.agent_trace)
                self._update_size()
                logger.info(f"Restored context from snapshot {snapshot_id}")
                return True

        logger.warning(f"Snapshot {snapshot_id} not found")
        return False

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots.

        Returns
        -------
        List[Dict[str, Any]]
            List of snapshot metadata
        """
        return [
            {
                "timestamp": snapshot.timestamp,
                "size_bytes": snapshot.size_bytes,
                "compressed": snapshot.compressed,
                "agents_present": list(snapshot.agent_outputs.keys()),
            }
            for snapshot in self.snapshots
        ]

    def clear_snapshots(self) -> None:
        """Clear all stored snapshots to free memory."""
        snapshot_count = len(self.snapshots)
        self.snapshots.clear()
        logger.info(f"Cleared {snapshot_count} snapshots")

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get detailed memory usage information.

        Returns
        -------
        Dict[str, Any]
            Memory usage statistics
        """
        return {
            "total_size_bytes": self.current_size,
            "agent_outputs_size": self.compression_manager.calculate_size(
                self.agent_outputs
            ),
            "agent_trace_size": self.compression_manager.calculate_size(
                self.agent_trace
            ),
            "snapshots_count": len(self.snapshots),
            "snapshots_total_size": sum(s.size_bytes for s in self.snapshots),
            "retrieved_notes_size": self.compression_manager.calculate_size(
                self.retrieved_notes or []
            ),
            "context_id": self.context_id,
        }

    def optimize_memory(self) -> Dict[str, Any]:
        """Optimize memory usage by cleaning up old data.

        Returns
        -------
        Dict[str, Any]
            Statistics about the optimization
        """
        before_size = self.current_size
        before_snapshots = len(self.snapshots)

        # Keep only the 5 most recent snapshots
        if len(self.snapshots) > 5:
            self.snapshots = self.snapshots[-5:]

        # Compress context if needed
        config = get_config()
        max_size = getattr(config.testing, "max_context_size_bytes", 1024 * 1024)
        if self.current_size > max_size:
            self._compress_context(max_size)

        self._update_size()

        stats = {
            "size_before": before_size,
            "size_after": self.current_size,
            "size_reduction_bytes": before_size - self.current_size,
            "snapshots_before": before_snapshots,
            "snapshots_after": len(self.snapshots),
            "snapshots_removed": before_snapshots - len(self.snapshots),
        }

        logger.info(f"Memory optimization completed: {stats}")
        return stats

    def mark_agent_error(self, agent_name: str, exc: Exception) -> None:
        agent = self._canon_agent(agent_name)
        info = self.agent_executions.get(agent) or AgentExecutionInfo(agent=agent)
        info.error_type = type(exc).__name__
        info.error_message = str(exc)
        self.agent_executions[agent] = info

    def clone(self) -> "AgentContext":
        """Create a deep copy of the context for parallel processing.

        Returns
        -------
        AgentContext
            A new context instance with copied data
        """
        cloned = AgentContext(
            query=self.query,
            retrieved_notes=deepcopy(self.retrieved_notes),
            agent_outputs=deepcopy(self.agent_outputs),
            user_config=deepcopy(self.user_config),
            final_synthesis=self.final_synthesis,
            agent_trace=deepcopy(self.agent_trace),
        )
        cloned.context_id = f"{self.context_id}_clone_{datetime.now().microsecond}"
        logger.debug(f"Cloned context {self.context_id} to {cloned.context_id}")
        return cloned

    def model_copy(
        self, *, update: Optional[Mapping[str, Any]] = None, deep: bool = False
    ) -> "AgentContext":
        """Override Pydantic's model_copy to ensure context_id regeneration."""
        # Create the copy using parent's model_copy
        copied = super().model_copy(update=update, deep=deep)

        # Always regenerate context_id for copies unless explicitly provided in update
        if not update or "context_id" not in update:
            copied.context_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[
                :8
            ]

        # Reinitialize compression manager and update size
        copied._compression_manager = ContextCompressionManager()
        copied._update_size()

        return copied

    # LangGraph-compatible execution state management

    def start_agent_execution(self, agent_name: str, step_id: str) -> None:
        info = self.agent_executions.get(agent_name) or {}
        info.update({
            "agent": agent_name,
            "step_id": step_id,
            "started": True,
            "completed": False,
            "success": None,
        })
        self.agent_executions[agent_name] = info

    def complete_agent_execution(self, agent_name: str, success: bool) -> None:
        info = self.agent_executions.get(agent_name) or {"agent": agent_name}
        info.update({
            "completed": True,
            "success": bool(success),
        })
        self.agent_executions[agent_name] = info

    def get_agent_execution(self, agent_name: str):
        # return a small object or dict; simplest is dict:
        return self.agent_executions.get(agent_name)

    def set_agent_dependencies(self, agent_name: str, dependencies: List[str]) -> None:
        """
        Set dependencies for an agent (used for conditional execution).

        Parameters
        ----------
        agent_name : str
            Name of the agent
        dependencies : List[str]
            List of agent names this agent depends on
        """
        agent = self._canon_agent(agent_name)
        self.agent_dependencies[agent] = dependencies
        logger.debug(f"Set dependencies for '{agent}': {dependencies}")

    def check_agent_dependencies(self, agent_name: str) -> Dict[str, bool]:
        """
        Check if an agent's dependencies are satisfied.

        Parameters
        ----------
        agent_name : str
            Name of the agent to check

        Returns
        -------
        Dict[str, bool]
            Dictionary mapping dependency names to satisfaction status
        """
        agent = self._canon_agent(agent_name)
        dependencies = self.agent_dependencies.get(agent, [])
        return {dep: dep in self.successful_agents for dep in dependencies}

    def can_agent_execute(self, agent_name: str) -> bool:
        """
        Check if an agent can execute based on its dependencies.

        Parameters
        ----------
        agent_name : str
            Name of the agent to check

        Returns
        -------
        bool
            True if all dependencies are satisfied, False otherwise
        """
        agent = self._canon_agent(agent_name)
        dependency_status = self.check_agent_dependencies(agent)
        return all(dependency_status.values())

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get a summary of execution state for all agents.

        Returns
        -------
        Dict[str, Any]
            Summary of agent execution states
        """
        return {
            "total_agents": len(self.agent_execution_status),
            "successful_agents": list(self.successful_agents),
            "failed_agents": list(self.failed_agents),
            "running_agents": [
                name
                for name, status in self.agent_execution_status.items()
                if status == "running"
            ],
            "pending_agents": [
                name
                for name, status in self.agent_execution_status.items()
                if status == "pending"
            ],
            "overall_success": self.success,
            "context_id": self.context_id,
        }

    # Agent isolation methods

    def _track_mutation(self, agent_name: str, field_name: str) -> None:
        """Track which agent modified which field for isolation purposes."""
        agent = self._canon_agent(agent_name)

        if agent not in self.agent_mutations:
            self.agent_mutations[agent] = []
        self.agent_mutations[agent].append(field_name)

    def _check_field_isolation(self, agent_name: str, field_name: str) -> bool:
        """
        Check if an agent can modify a field based on isolation rules.

        Parameters
        ----------
        agent_name : str
            Name of the agent attempting modification
        field_name : str
            Name of the field being modified

        Returns
        -------
        bool
            True if modification is allowed, False otherwise
        """
        agent = self._canon_agent(agent_name)

        # Check if field is locked
        if field_name in self.locked_fields:
            return False

        # Check if another agent already owns this field
        for other_agent, mutations in self.agent_mutations.items():
            if other_agent != agent and field_name in mutations:
                logger.warning(
                    f"Agent '{agent}' attempting to modify field '{field_name}' "
                    f"already modified by '{other_agent}'"
                )
                return False

        return True

    def lock_field(self, field_name: str) -> None:
        """
        Lock a field to prevent further modifications.

        Parameters
        ----------
        field_name : str
            Name of the field to lock
        """
        self.locked_fields.add(field_name)
        logger.debug(f"Locked field '{field_name}' from further modifications")

    def unlock_field(self, field_name: str) -> None:
        """
        Unlock a previously locked field.

        Parameters
        ----------
        field_name : str
            Name of the field to unlock
        """
        self.locked_fields.discard(field_name)
        logger.debug(f"Unlocked field '{field_name}' for modifications")

    def add_agent_output_isolated(self, agent_name: str, output: Any) -> bool:
        """
        Add agent output with isolation checking.

        Parameters
        ----------
        agent_name : str
            Name of the agent
        output : Any
            Output to add

        Returns
        -------
        bool
            True if addition was successful, False if blocked by isolation rules
        """
        agent = self._canon_agent(agent_name)

        # --- hard per-agent caps (fast path) ---
        cap = self.OUTPUT_CHAR_CAPS.get(agent.lower())
        if cap and isinstance(output, str):
            output = output[:cap]

        field_name = f"agent_outputs.{agent}"

        if not self._check_field_isolation(agent, field_name):
            logger.error(
                f"Agent '{agent}' blocked from modifying its output due to isolation rules"
            )
            return False

        # Check if this agent has already modified this field (prevents multiple modifications)
        agent_mutations = self.agent_mutations.get(agent, [])
        if field_name in agent_mutations:
            logger.error(
                f"Agent '{agent}' already modified field '{field_name}', multiple modifications not allowed"
            )
            return False

        # --- hard per-agent caps (fast path) ---
        output = self._cap_agent_output(agent, output)

        self.agent_outputs[agent] = output
        self._track_mutation(agent, field_name)
        self._update_size()
        self._check_size_limits()
        logger.info(f"Added output for agent '{agent}': {str(output)[:100]}...")
        return True

    def get_agent_mutation_history(self) -> Dict[str, List[str]]:
        """
        Get the history of field mutations by each agent.

        Returns
        -------
        Dict[str, List[str]]
            Dictionary mapping agent names to lists of fields they modified
        """
        return dict(self.agent_mutations)

    # Enhanced snapshot methods with execution state

    def create_execution_snapshot(self, label: Optional[str] = None) -> str:
        """
        Create a snapshot that includes execution state for LangGraph compatibility.

        Parameters
        ----------
        label : str, optional
            Optional label for the snapshot

        Returns
        -------
        str
            Snapshot ID for later restoration
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot_id = f"{timestamp}_{len(self.snapshots)}"

        # Enhanced snapshot with execution state
        snapshot_data = {
            "context_id": self.context_id,
            "timestamp": timestamp,
            "query": self.query,
            "agent_outputs": deepcopy(self.agent_outputs),
            "retrieved_notes": deepcopy(self.retrieved_notes),
            "user_config": deepcopy(self.user_config),
            "final_synthesis": self.final_synthesis,
            "agent_trace": deepcopy(self.agent_trace),
            "size_bytes": self.current_size,
            "execution_state": deepcopy(self.execution_state),
            "agent_execution_status": dict(self.agent_execution_status),
            "successful_agents": set(self.successful_agents),
            "failed_agents": set(self.failed_agents),
            "agent_dependencies": deepcopy(self.agent_dependencies),
            "success": self.success,
            "agent_mutations": deepcopy(self.agent_mutations),
            "locked_fields": set(self.locked_fields),
        }

        try:
            snapshot = ContextSnapshot(
                context_id=self.context_id,
                timestamp=timestamp,
                query=self.query,
                agent_outputs=deepcopy(self.agent_outputs),
                retrieved_notes=deepcopy(self.retrieved_notes),
                user_config=deepcopy(self.user_config),
                final_synthesis=self.final_synthesis,
                agent_trace=deepcopy(self.agent_trace),
                size_bytes=self.current_size,
            )

            # Store extended data in a separate field
            snapshot.compressed = False  # Mark as having extended data

            self.snapshots.append(snapshot)

            # Store execution state in execution_state for this snapshot
            self.execution_state[f"snapshot_{snapshot_id}_execution_data"] = (
                snapshot_data
            )

            logger.info(
                f"Created execution snapshot {snapshot_id}"
                + (f" with label '{label}'" if label else "")
            )
            return snapshot_id

        except Exception as e:
            logger.error(f"Failed to create execution snapshot: {e}")
            raise StateTransitionError(
                transition_type="snapshot_creation_failed",
                state_details=str(e),
                step_id=snapshot_id,
                agent_id="context_manager",
                cause=e,
            )

    def restore_execution_snapshot(self, snapshot_id: str) -> bool:
        """
        Restore context including execution state from a snapshot.

        Parameters
        ----------
        snapshot_id : str
            The snapshot ID to restore

        Returns
        -------
        bool
            True if restoration was successful, False otherwise
        """
        try:
            # First try standard snapshot restoration
            if self.restore_snapshot(snapshot_id):
                # Then restore execution state if available
                execution_data_key = f"snapshot_{snapshot_id}_execution_data"
                if execution_data_key in self.execution_state:
                    snapshot_data = self.execution_state[execution_data_key]

                    self.execution_state = deepcopy(
                        snapshot_data.get("execution_state", {})
                    )
                    self.agent_execution_status = dict(
                        snapshot_data.get("agent_execution_status", {})
                    )
                    self.successful_agents = set(
                        snapshot_data.get("successful_agents", set())
                    )
                    self.failed_agents = set(snapshot_data.get("failed_agents", set()))
                    self.agent_dependencies = deepcopy(
                        snapshot_data.get("agent_dependencies", {})
                    )
                    self.success = snapshot_data.get("success", True)
                    self.agent_mutations = deepcopy(
                        snapshot_data.get("agent_mutations", {})
                    )
                    self.locked_fields = set(snapshot_data.get("locked_fields", set()))

                    logger.info(f"Restored execution state from snapshot {snapshot_id}")

                return True

            return False

        except Exception as e:
            logger.error(f"Failed to restore execution snapshot {snapshot_id}: {e}")
            raise StateTransitionError(
                transition_type="snapshot_restore_failed",
                from_state="current",
                to_state=snapshot_id,
                state_details=str(e),
                step_id=snapshot_id,
                agent_id="context_manager",
                cause=e,
            )

    def get_rollback_options(self) -> List[Dict[str, Any]]:
        """
        Get available rollback options with execution state info.

        Returns
        -------
        List[Dict[str, Any]]
            List of available rollback points with metadata
        """
        options = []
        for snapshot in self.snapshots:
            execution_data_key = (
                f"snapshot_{snapshot.timestamp}_{len(self.snapshots)}_execution_data"
            )
            execution_data = self.execution_state.get(execution_data_key, {})

            options.append(
                {
                    "snapshot_id": f"{snapshot.timestamp}_{len(self.snapshots)}",
                    "timestamp": snapshot.timestamp,
                    "size_bytes": snapshot.size_bytes,
                    "successful_agents": list(
                        execution_data.get("successful_agents", [])
                    ),
                    "failed_agents": list(execution_data.get("failed_agents", [])),
                    "overall_success": execution_data.get("success", True),
                    "agents_count": len(snapshot.agent_outputs),
                }
            )

        return options

    def add_execution_edge(
            self,
            from_agent: str,
            to_agent: str,
            edge_type: str = "normal",
            condition: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an execution edge for LangGraph DAG compatibility.
        """
        from_a = self._canon_agent(from_agent)
        to_a = self._canon_agent(to_agent)

        edge = {
            "from_agent": from_a,
            "to_agent": to_a,
            "edge_type": edge_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "condition": condition,
            "metadata": metadata or {},
        }
        self.execution_edges.append(edge)
        logger.debug(f"Added execution edge: {from_a} -> {to_a} ({edge_type})")

    def record_conditional_routing(
        self,
        decision_point: str,
        condition: str,
        chosen_path: str,
        alternative_paths: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record conditional routing decision for LangGraph DAG mapping.

        Parameters
        ----------
        decision_point : str
            Where the routing decision was made
        condition : str
            The condition that was evaluated
        chosen_path : str
            The path that was chosen
        alternative_paths : List[str]
            Paths that were not taken
        metadata : Optional[Dict[str, Any]]
            Additional routing metadata
        """
        routing_record = {
            "decision_point": decision_point,
            "condition": condition,
            "chosen_path": chosen_path,
            "alternative_paths": alternative_paths,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        if decision_point not in self.conditional_routing:
            self.conditional_routing[decision_point] = []
        self.conditional_routing[decision_point].append(routing_record)

        logger.debug(
            f"Recorded conditional routing at {decision_point}: chose {chosen_path}"
        )

    def set_path_metadata(self, key: str, value: Any) -> None:
        """
        Set execution path metadata for LangGraph compatibility.

        Parameters
        ----------
        key : str
            Metadata key
        value : Any
            Metadata value
        """
        self.path_metadata[key] = value
        logger.debug(f"Set path metadata: {key} = {value}")

    def get_execution_graph(self) -> Dict[str, Any]:
        """
        Get execution graph representation for LangGraph compatibility.
        """
        nodes = []
        for agent_name in self.agent_outputs.keys():
            canon = self._canon_agent(agent_name)

            # Prefer canonical keys, but fall back to legacy keys if present
            status = self.agent_execution_status.get(canon) or self.agent_execution_status.get(agent_name, "unknown")

            nodes.append(
                {
                    "id": canon,  # or keep agent_name if you want to preserve original display
                    "type": "agent",
                    "status": status,
                    "success": (canon in self.successful_agents) or (agent_name in self.successful_agents),
                    "failed": (canon in self.failed_agents) or (agent_name in self.failed_agents),
                }
            )

        return {
            "nodes": nodes,
            "edges": self.execution_edges,
            "conditional_routing": self.conditional_routing,
            "path_metadata": self.path_metadata,
            "execution_summary": {
                "total_agents": len(nodes),
                "successful_agents": len(self.successful_agents),
                "failed_agents": len(self.failed_agents),
                "success_rate": (len(self.successful_agents) / len(nodes) if nodes else 0),
            },
        }
