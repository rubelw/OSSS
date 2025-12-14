# src/OSSS/ai/agents/base.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field, ConfigDict


# ======================================================================
# AgentContext
# ======================================================================
class AgentContext(BaseModel):
    """
    The **canonical universal input object** for all agents in the OSSS
    conversational AI system.

    --------------------------------------------------------------------
    Why AgentContext Exists
    --------------------------------------------------------------------
    Without a single shared contract for what agents receive:
        - Each agent would invent its own argument types
        - The orchestrator would have to special-case every agent
        - Multi-agent chaining would become impossible
        - State and metadata would fragment across modules

    AgentContext solves this by standardizing:
        - The current user message
        - Routing information and classifier output
        - Multi-turn chaining metadata
        - RAG retrieval context
        - Extensible metadata for future capabilities

    Any agent, no matter how complex or simple, receives **the same shape**
    of contextual information.

    --------------------------------------------------------------------
    Field-by-field explanation
    --------------------------------------------------------------------
    query : str
        The *raw* natural language message for THIS turn.
        This is what the agent should treat as the user's instruction.

    session_id : str
        The global "orchestrator session".
        - Stable for the entire chat session.
        - Different from subagent sessions (e.g., registration sessions).
        - Useful for telemetry, logs, memory persistence, etc.

    agent_id / agent_name : Optional[str]
        These identify the agent producing a result.
        They allow:
            - UI labeling
            - agent chaining (“which agent produced this answer?”)
            - debugging / attribution

        If None, the orchestrator or agent may fill them in.

    intent / action / action_confidence :
        High-level routing information.
        Examples:
            - intent="register_new_student"
            - action="fetch-course-list"
            - action_confidence=0.76

        Agents may choose to override these when returning results.

    main_session_id : Optional[str]
        Identifier assigned when a RAG conversational session is started.
        Used to maintain RAG continuity across multiple turns.

    subagent_session_id : Optional[str]
        If the user is in a multi-turn workflow (wizard-style) handled by a
        particular subagent, the subagent stores its continuation state under
        this session id.

        Example:
            - Starting a registration process creates subagent_session_id="abc123"
            - All subsequent turns incoming to the registration agent reuse this id

    metadata : Dict[str, Any]
        Free-form extensible structured data.
        Used for:
            - contextual variables ("timezone", "school_district")
            - toggles ("debug_mode")
            - role info ("user_role": "teacher")

    retrieved_chunks : List[Dict[str, Any]]
        RAG retrieval results already fetched by the orchestrator.
        Agents may read these or pass them forward.
        The UI "Sources" panel uses them.
    """

    # ---- Required fields -----------------------------------------------------
    query: str
    session_id: str

    # ---- Agent identity (optional but recommended) ---------------------------
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

    # ---- High-level routing metadata -----------------------------------------
    intent: Optional[str] = None
    action: Optional[str] = None
    action_confidence: Optional[float] = None

    # ---- Multi-turn session chaining -----------------------------------------
    main_session_id: Optional[str] = None
    subagent_session_id: Optional[str] = None
    session_files: List[str] = Field(default_factory=list)



    # ---- Arbitrary structured metadata ---------------------------------------
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # ---- RAG retrieval context -----------------------------------------------
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)


# ======================================================================
# AgentResult
# ======================================================================
class AgentResult(BaseModel):
    """
    **Universal output contract** for all agents.
    (docstring unchanged)
    """

    # Pydantic v2 config
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,  # allows constructing via field name even if alias exists
    )

    # ---- Human-facing answer -------------------------------------------------
    # Canonical field is answer_text; allow legacy `text=` as an alias.
    answer_text: str = Field(..., alias="text")

    # ---- High-level metadata -------------------------------------------------
    intent: Optional[str] = None
    index: Optional[str] = None

    # ---- Identity of producing agent ----------------------------------------
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

    # ---- Processing state ----------------------------------------------------
    status: str = "ok"

    # ---- Optional provenance chunks -----------------------------------------
    extra_chunks: List[Dict[str, Any]] = Field(default_factory=list)

    # ---- Token for multi-turn subagent workflows -----------------------------
    agent_session_id: Optional[str] = None

    # ---- Machine-readable payload -------------------------------------------
    data: Dict[str, Any] = Field(default_factory=dict)

    # ---- Downstream agent results -------------------------------------------
    children: List["AgentResult"] = Field(default_factory=list)

# ======================================================================
# Agent Protocol
# ======================================================================
class Agent(Protocol):
    """
    Minimal behavioral contract every agent must satisfy.

    --------------------------------------------------------------------
    Why a Protocol?
    --------------------------------------------------------------------
    - Enables static typing & IDE autocompletion
    - Ensures every agent implements:
        * intent_name
        * async run(ctx)
    - Does NOT enforce a shared base class (no inheritance required)
    - Lightweight and flexible

    This keeps the system:
        - Plugin-friendly
        - Extensible
        - Easy to test
        - Compatible with dynamic imports / registration decorators

    --------------------------------------------------------------------
    Required attributes
    --------------------------------------------------------------------
    intent_name : str
        Name used by:
            - router
            - intent classifier
            - orchestrator
            - logging

        Must be globally unique across the agent registry.

    async def run(ctx: AgentContext) -> AgentResult
        Execute agent logic and return the complete AgentResult.
        This function should be:
          - deterministic (given ctx)
          - pure (no global state writes)
          - idempotent (ideally)
          - fully asynchronous (IO-safe, except trivial CPU work)

    --------------------------------------------------------------------
    Implementation example
    --------------------------------------------------------------------
        class HelloAgent:
            intent_name = "hello"

            async def run(self, ctx):
                return AgentResult(answer_text="Hi there!")
    """

    intent_name: str

    async def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover
        ...
