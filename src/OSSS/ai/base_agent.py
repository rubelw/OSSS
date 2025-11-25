# src/OSSS/ai/agents/base_agent.py
from __future__ import annotations

from typing import Any, Dict, Optional, Generic, TypeVar
from pydantic import BaseModel

from OSSS.ai.agents import AgentContext, AgentResult, register_agent
from OSSS.ai.agents.reasoning import ReasoningTraceMixin, ReasoningStep

StateT = TypeVar("StateT", bound=BaseModel)


class OSSSAgent(ReasoningTraceMixin):
    """
    Base class for all OSSS agents.

    - Provides a common interface for .run(ctx)
    - Carries reasoning steps via ReasoningTraceMixin
    - Expects subclasses to set `intent_name` and implement `run()`.
    """

    # Each concrete agent MUST set this to match the router’s intent label.
    intent_name: str

    async def run(self, ctx: AgentContext) -> AgentResult:
        """
        Must be implemented by subclasses.

        It should:
          - inspect ctx (query, session IDs, metadata, etc.)
          - perform any reasoning/slot-filling/service calls
          - return an AgentResult
        """
        raise NotImplementedError


class SlotFillingAgent(OSSSAgent, Generic<StateT]):
    """
    Opinionated base for agents that:
      - Maintain a per-session state object (slots)
      - Decide whether to prompt the user vs. call a backend service
      - Emit a structured AgentResult with reasoning trace

    You plug in:
      - State model (StateT)
      - Storage (get_state / save_state)
      - Domain logic (update_state_from_turn, should_call_service, call_service, build_prompt)
    """

    state_cls: type[StateT]

    # ---- Session & state management hooks -----------------------------

    def get_session_id(self, ctx: AgentContext) -> str:
        """
        Decide which ID to use as the 'subagent session' for this agent.
        Default: subagent_session_id or main session_id.
        """
        return ctx.subagent_session_id or ctx.session_id

    async def load_state(self, session_id: str) -> StateT:
        """
        Load or initialize state for this session.
        Override to plug into your own RegistrationStateStore, etc.
        """
        return self.state_cls(session_id=session_id)  # type: ignore[arg-type]

    async def save_state(self, state: StateT) -> None:
        """
        Persist state after each turn.
        Override to use your DB, Redis, etc.
        """
        # Default: no-op
        return None

    # ---- Domain-specific hooks ---------------------------------------

    async def update_state_from_turn(self, ctx: AgentContext, state: StateT) -> None:
        """
        Extract entities/slots from ctx.query (and maybe other context),
        then mutate `state` in-place.
        """
        raise NotImplementedError

    async def should_call_service(self, ctx: AgentContext, state: StateT) -> bool:
        """
        Decide whether we have enough info to call the backend service.
        """
        raise NotImplementedError

    async def call_service(self, ctx: AgentContext, state: StateT) -> str:
        """
        Perform the side-effectful call (HTTP, DB, etc.) and return user-visible text.
        """
        raise NotImplementedError

    async def build_prompt(self, ctx: AgentContext, state: StateT) -> str:
        """
        Build the message to show the user when we STILL need information.
        """
        raise NotImplementedError

    # ---- Template method: shared .run() implementation ----------------

    async def run(self, ctx: AgentContext) -> AgentResult:
        """
        Orchestrates the full turn:

        1) choose session_id
        2) load state
        3) update state using this turn
        4) decide: call service or prompt
        5) persist state
        6) build AgentResult with reasoning trace + debug info
        """
        session_id = self.get_session_id(ctx)

        self.add_reasoning_step(
            phase="session_mode",
            thought="Determine which registration session ID to use for this turn.",
            action="get_session_id(ctx)",
            observation={
                "session_id": session_id,
                "ctx_session_id": ctx.session_id,
                "ctx_subagent_session_id": ctx.subagent_session_id,
            },
        )

        state = await self.load_state(session_id)

        self.add_reasoning_step(
            phase="load_state",
            thought="Load or initialize state for this session.",
            action="load_state(session_id)",
            observation={
                "state_repr": repr(state),
            },
        )

        # Update state with this turn's text
        await self.update_state_from_turn(ctx, state)

        self.add_reasoning_step(
            phase="extract_slots",
            thought="Update state from the user's current query.",
            action="update_state_from_turn(ctx, state)",
            observation={"state_repr_after_update": repr(state)},
        )

        # Decide whether to call the backend service
        proceed = await self.should_call_service(ctx, state)

        self.add_reasoning_step(
            phase="dialog_policy",
            thought="Decide whether to call backend service or prompt for more info.",
            action="should_call_service(ctx, state)",
            observation={"proceed": proceed},
        )

        if proceed:
            answer_text = await self.call_service(ctx, state)
            status = "ok"
            phase = "service_call"
        else:
            answer_text = await self.build_prompt(ctx, state)
            status = "needs_input"
            phase = "prompt"

        self.add_reasoning_step(
            phase=phase,
            thought="Build final user-facing message for this turn.",
            action="call_service/build_prompt",
            observation={"answer_preview": answer_text[:200]},
        )

        # Persist state
        await self.save_state(state)

        # Bundle debug info
        debug_info: Dict[str, Any] = {
            "session_id": session_id,
            "state_repr": repr(state),
            "reasoning_steps": [rs.model_dump() for rs in self.reasoning_steps],
        }

        return AgentResult(
            answer_text=answer_text,
            status=status,
            intent=self.intent_name,
            agent_id=getattr(ctx, "agent_id", None),
            agent_name=getattr(ctx, "agent_name", self.intent_name),
            extra_chunks=[],
            data={"agent_debug_information": debug_info},
            children=[],
        )
