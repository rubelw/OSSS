# src/OSSS/ai/agents/base.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """
    Context passed into each agent in a chain.

    - query: the natural-language user query for THIS turn
    - session_id: the "current" session id from the orchestrator
    - main_session_id: the top-level RAG session id
    - subagent_session_id: if we are continuing a subagent workflow
    - intent/action: high-level classification from the orchestrator
    - metadata: arbitrary extra fields you might want to attach
    - retrieved_chunks: RAG chunks already fetched by the orchestrator
    """

    query: str
    session_id: str

    # Identity of the calling / current agent
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

    # High-level routing info
    intent: Optional[str] = None
    action: Optional[str] = None
    action_confidence: Optional[float] = None

    # Chaining info
    main_session_id: Optional[str] = None
    subagent_session_id: Optional[str] = None

    # Arbitrary metadata / RAG context
    metadata: Dict[str, Any] = Field(default_factory=dict)
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)


class AgentResult(BaseModel):
    """
    Standard result from any agent in the chain.

    - answer_text: what should be shown to the user (top-level)
    - intent: final / effective intent
    - index: which RAG index or logical domain this came from
    - status: "ok" | "error" | custom
    - extra_chunks: optional RAG-style chunks for debug / "Sources" UI
    - agent_session_id: subagent session id (for continuations)
    - data: structured payload for downstream agents / logging
    - children: nested AgentResult objects (downstream agents in chain)
    """

    answer_text: str

    intent: Optional[str] = None
    index: Optional[str] = None

    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

    status: str = "ok"

    extra_chunks: List[Dict[str, Any]] = Field(default_factory=list)

    # NOTE: for subagent continuation, this is the NEW subagent session id
    agent_session_id: Optional[str] = None

    # Structured payload
    data: Dict[str, Any] = Field(default_factory=dict)

    # Agent chain: children = downstream agents that were called
    children: List["AgentResult"] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class Agent(Protocol):
    """
    Minimal protocol all agents should follow.
    """

    intent_name: str

    async def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover - interface
        ...
