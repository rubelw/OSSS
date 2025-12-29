from __future__ import annotations

from typing import List, Optional, Dict, Any, TYPE_CHECKING

from pydantic import BaseModel, Field, ConfigDict

# Type-only import to avoid circular import at runtime.
# This lets IDEs / type checkers know about the external definition
# without actually importing orchestration during module import.
if TYPE_CHECKING:
    from OSSS.ai.orchestration.models_internal import AgentOutputEnvelope as _AgentOutputEnvelopeExternal


class AgentOutputEnvelope(BaseModel):
    """
    Canonical representation of a single agent's output.

    This is the "one true" internal format. Everything else
    (agent_outputs dict, execution_state mirrors, API payloads)
    is derived from this.
    """

    agent_name: str = Field(description="Full agent name (may include suffixes)")
    logical_name: str = Field(
        description="Logical agent key used in orchestration (e.g. 'refiner', 'data_query')"
    )
    content: Any = Field(description="Renderable content from the agent")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Non-rendered metadata (intent, tone, wizard state, etc.)"
    )

    # Optional, but useful for UX and downstream routing
    role: Optional[str] = Field(
        default=None,
        description="Semantic role of this output (e.g. 'assistant', 'system', 'tool')"
    )
    action: Optional[str] = Field(
        default=None,
        description="High-level action type (e.g. 'read', 'create', 'update', 'wizard_step')"
    )
    intent: Optional[str] = Field(
        default=None,
        description="Intent tag (e.g. 'answer', 'clarify', 'consent_create')"
    )
    tone: Optional[str] = Field(
        default=None,
        description="Tone tag (e.g. 'informal', 'formal', 'empathetic')"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def preview(self) -> str:
        """Short preview of content for logging / UIs."""
        text = str(self.content)
        return text[:120] + ("…" if len(text) > 120 else "")

    def as_public_dict(self) -> Dict[str, Any]:
        """
        Dict form safe for API export (no internal-only fields).
        """
        data = self.model_dump()
        # nothing special to strip (yet), but this keeps the call site clean
        return data


class AgentContext:
    """
    Lightweight shared context object passed between agents and orchestrator.

    Responsibilities:
      - Hold execution_state (shared mutable dict)
      - Hold a simple agent_outputs mapping (logical_name -> last content)
      - Hold a canonical list of AgentOutputEnvelope objects
      - Provide helper accessors used by agents (e.g. data_query) and orchestrator
    """

    def __init__(
        self,
        query: str | None = None,
        execution_state: Optional[Dict[str, Any]] = None,
        agent_outputs: Optional[Dict[str, Any]] = None,
        intent: Optional[str] = None,
        **extra: Any,
    ) -> None:
        # Original user query (optional but nice to have)
        self.query: str = (query or "").strip()

        self.successful_agents: list[str] = []
        self.failed_agents: list[str] = []

        # Shared mutable state across agents
        self.execution_state: Dict[str, Any] = execution_state or {}

        # Simple mapping used by orchestrator and API: logical_name -> content
        self.agent_outputs: Dict[str, Any] = agent_outputs or {}

        # Optional high-level intent (can be set by classifier/orchestrator)
        self.intent: Optional[str] = intent

        # Canonical envelopes list (internal)
        self._agent_output_envelopes: List[AgentOutputEnvelope] = []

        # Any extra fields callers want to stash (non-breaking)
        self._extra: Dict[str, Any] = extra

    # ------------------------------------------------------------------
    # Envelope accessors
    # ------------------------------------------------------------------
    @property
    def output_envelopes(self) -> List[Dict[str, Any]]:
        """
        Public, serialization-friendly view of envelopes.

        Orchestration code treats each item either as Mapping (dict) or as an
        object with .agent_name / .logical_name / .content / .meta attributes.
        Returning dicts here keeps things simple.
        """
        return [env.as_public_dict() for env in self._agent_output_envelopes]

    @property
    def agent_output_envelopes(self) -> List[AgentOutputEnvelope]:
        """
        Backwards-compatible access used by some internals.

        Orchestrator code is defensive and can handle actual objects as well.
        """
        return self._agent_output_envelopes

    # ------------------------------------------------------------------
    # Core write API for agents
    # ------------------------------------------------------------------
    def add_agent_output(
        self,
        agent_name: str,
        content: Any = None,
        *,
        logical_name: Optional[str] = None,
        role: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> AgentOutputEnvelope:
        """
        Primary way agents should record output.

        Supports both:
          - add_agent_output("data_query", payload)
          - add_agent_output("data_query", payload, logical_name="data_query")
        """
        if content is None and meta is None:
            # if someone accidentally called with old positional style
            raise TypeError("add_agent_output requires at least content")

        logical = (logical_name or agent_name.split(":", 1)[0]).strip()

        envelope = AgentOutputEnvelope(
            agent_name=agent_name,
            logical_name=logical,
            content=content,
            meta=meta or {},
            role=role,
            action=action,
            intent=intent,
        )

        self._agent_output_envelopes.append(envelope)

        self.agent_outputs[logical] = content
        if agent_name != logical:
            self.agent_outputs[agent_name] = content

        idx = self.execution_state.setdefault("agent_output_index", {})
        idx[logical] = envelope.as_public_dict()
        idx[agent_name] = envelope.as_public_dict()

        return envelope

    def add_agent_output_envelope(
        self,
        envelope: AgentOutputEnvelope | Dict[str, Any],
    ) -> AgentOutputEnvelope:
        """
        Backwards-compatible helper if some code still constructs envelopes directly.
        """
        if isinstance(envelope, dict):
            envelope = AgentOutputEnvelope(**envelope)

        self._agent_output_envelopes.append(envelope)

        logical = envelope.logical_name or envelope.agent_name
        self.agent_outputs[logical] = envelope.content
        if envelope.agent_name != logical:
            self.agent_outputs[envelope.agent_name] = envelope.content

        idx = self.execution_state.setdefault("agent_output_index", {})
        idx[logical] = envelope.as_public_dict()
        idx[envelope.agent_name] = envelope.as_public_dict()

        return envelope

    # ------------------------------------------------------------------
    # Token usage helper (used by agents like RefinerAgent)
    # ------------------------------------------------------------------
    def add_agent_token_usage(
        self,
        agent_name: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Lightweight token accounting helper used by agents.

        Aggregates per-agent token usage into execution_state["token_usage"].
        Compatible with existing agents that call context.add_agent_token_usage.
        """
        try:
            name = (agent_name or "").strip() or "unknown"
        except Exception:
            name = "unknown"

        usage_root = self.execution_state.setdefault("token_usage", {})
        agent_usage = usage_root.get(name) or {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

        agent_usage["input_tokens"] += int(input_tokens or 0)
        agent_usage["output_tokens"] += int(output_tokens or 0)

        if total_tokens is None:
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        agent_usage["total_tokens"] += int(total_tokens or 0)

        usage_root[name] = agent_usage
        return agent_usage

    # ------------------------------------------------------------------
    # Convenience getters used by DataQueryAgent and friends
    # ------------------------------------------------------------------
    def get_last_output(self, key: str) -> Any:
        """
        Return the *content* of the most recent envelope whose logical_name
        matches `key` OR whose agent_name starts with f"{key}:".
        """
        needle = (key or "").strip().lower()
        if not needle:
            return None

        for env in reversed(self._agent_output_envelopes):
            ln = (env.logical_name or "").lower()
            an = (env.agent_name or "").lower()
            if ln == needle or an == needle or an.startswith(needle + ":"):
                return env.content

        # fallback to index in execution_state, if present
        idx = self.execution_state.get("agent_output_index") or {}
        entry = idx.get(key) or idx.get(f"{key}:")
        if isinstance(entry, dict):
            return entry.get("content")

        return None

    def get_classifier_result(self) -> Dict[str, Any]:
        """
        Canonical place to read classifier output. ClassificationService
        should stash into execution_state['classifier_result'].
        """
        val = self.execution_state.get("classifier_result") or {}
        return val if isinstance(val, dict) else {}

    def get_task_classification(self) -> Dict[str, Any]:
        val = self.execution_state.get("task_classification") or {}
        return val if isinstance(val, dict) else {}

    def get_cognitive_classification(self) -> Dict[str, Any]:
        val = self.execution_state.get("cognitive_classification") or {}
        return val if isinstance(val, dict) else {}

    def get_user_question(self) -> str:
        """
        Best-effort way to retrieve the original user question.
        """
        exec_state = self.execution_state or {}
        q = (
            exec_state.get("user_question")
            or exec_state.get("original_query")
            or self.query
            or ""
        )
        return str(q)

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------
    def as_debug_dict(self) -> Dict[str, Any]:
        """
        Safe debug view of this context for logging or inspection.
        """
        return {
            "query": self.query,
            "intent": self.intent,
            "execution_state_keys": list(self.execution_state.keys()),
            "agent_output_keys": list(self.agent_outputs.keys()),
            "envelope_count": len(self._agent_output_envelopes),
        }

    def __repr__(self) -> str:
        return f"AgentContext(query={self.query!r}, envelopes={len(self._agent_output_envelopes)})"
