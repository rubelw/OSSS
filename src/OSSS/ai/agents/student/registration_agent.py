from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional, List

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext
from .registration_state import RegistrationSessionState, RegistrationStateStore
from .registration_dialog import (
    decide_session_mode,
    evaluate_dialog_slots,
    DialogStepResult,
)
from .registration_client import RegistrationServiceClient

logger = logging.getLogger("OSSS.ai.agents.student.registration")


# ---------------------------------------------------------------------------
# Simple result object: router_agent only needs attributes via getattr
# ---------------------------------------------------------------------------
class RegistrationAgentResult:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Internal reasoning step representation
# ---------------------------------------------------------------------------
@dataclass
class ReasoningStep:
    phase: str
    thought: str
    action: str
    observation: Any | None = None


# ---------------------------------------------------------------------------
# Module-level singletons for state + client
# ---------------------------------------------------------------------------
_state_store = RegistrationStateStore()
_registration_client = RegistrationServiceClient()


@register_agent("register_new_student")
class RegisterNewStudentAgent:
    """
    Specialized agent that orchestrates multi-turn registration dialog.

    It:
      - Decides whether we’re starting a NEW registration or CONTINUING one.
      - Loads & updates RegistrationSessionState from a store.
      - Uses dialog policy to decide whether to prompt or proceed.
      - Optionally calls the RegistrationServiceClient (currently disabled in favor
        of a simple thank-you + handoff back to general RAG once the dialog is complete).
      - Returns a RegistrationAgentResult with debug trace for the UI.
    """

    def __init__(self) -> None:
        # Keep a per-call reasoning trace (reset on each run)
        self._reasoning_steps: List[ReasoningStep] = []

    # ------------------------------------------------------------------
    # Reasoning helpers
    # ------------------------------------------------------------------
    def reset_reasoning(self) -> None:
        self._reasoning_steps = []

    def append_reasoning_step(
        self,
        *,
        phase: str,
        thought: str,
        action: str,
        observation: Any | None = None,
    ) -> None:
        self._reasoning_steps.append(
            ReasoningStep(
                phase=phase,
                thought=thought,
                action=action,
                observation=observation,
            )
        )

    def update_last_observation(self, observation: Any) -> None:
        if not self._reasoning_steps:
            return
        self._reasoning_steps[-1].observation = observation

    def export_reasoning(self) -> list[dict[str, Any]]:
        return [asdict(step) for step in self._reasoning_steps]

    # ------------------------------------------------------------------
    # Core entrypoint
    # ------------------------------------------------------------------
    async def run(self, ctx: AgentContext) -> Any:
        """
        Main agent entrypoint called by the router.

        Returns a RegistrationAgentResult with:
          - answer_text
          - status
          - intent
          - agent_session_id
          - agent_id / agent_name
          - data.agent_debug_information (for the UI)
        """
        self.reset_reasoning()

        # -------------------------------
        # 1) Decide session mode + id
        # -------------------------------
        self.append_reasoning_step(
            phase="session_mode",
            thought=(
                "Decide whether this turn starts a NEW registration or "
                "CONTINUES an existing one, and pick the active session_id."
            ),
            action="decide_session_mode(ctx)",
            observation=None,
        )

        session_mode, session_id = decide_session_mode(ctx)
        self.update_last_observation(
            {
                "session_mode": session_mode,
                "session_id": session_id,
                "existing_subagent_session_id": ctx.subagent_session_id,
            }
        )

        # Fallback: if decide_session_mode didn’t give us an id, derive one.
        if not session_id:
            session_id = ctx.subagent_session_id or ctx.session_id

        # -------------------------------
        # 2) Load or create session state
        # -------------------------------
        self.append_reasoning_step(
            phase="load_state",
            thought=(
                "Load any prior RegistrationSessionState for this session_id so "
                "we can continue slot-filling across turns."
            ),
            action="state_store.get(session_id)",
            observation=None,
        )

        state = await _state_store.get(session_id)
        if state is None:
            state = RegistrationSessionState(session_id=session_id)
            found_existing = False
        else:
            found_existing = True

        # Keep track of dialog mode in the persisted state
        if session_mode is not None:
            state.session_mode = session_mode

        self.update_last_observation(
            {
                "found_existing_state": found_existing,
                "state_repr": repr(state),
            }
        )

        # -------------------------------
        # 3) Dialog policy / slot filling
        # -------------------------------
        self.append_reasoning_step(
            phase="dialog_policy",
            thought=(
                "Given the current session_mode and session_state, decide whether "
                "we have enough information to finish the registration dialog, or "
                "whether we must prompt the user for missing fields."
            ),
            action="evaluate_dialog_slots(...)",
            observation=None,
        )

        dialog_result: DialogStepResult = await evaluate_dialog_slots(
            ctx=ctx,
            session_mode=session_mode,
            session_state=state,
            state_store=_state_store,
        )

        self.update_last_observation(
            {
                "proceed": dialog_result.proceed,
                "prompt_phase": dialog_result.prompt_phase,
                "prompt_status": dialog_result.prompt_status,
                "has_prompt": bool(dialog_result.prompt_answer_text),
            }
        )

        resolved_state = dialog_result.session_state or state

        # Ensure the resolved_state also has session_mode set (until completion)
        resolved_state.session_mode = session_mode

        # -------------------------------
        # 4) Build debug info blob
        # -------------------------------
        debug_info: dict[str, Any] = {
            "phase": dialog_result.prompt_phase
            or ("proceed" if dialog_result.proceed else "unknown"),
            "query": ctx.query,
            "session_mode": session_mode,
            "existing_registration_session_id": ctx.subagent_session_id,
            "registration_session_id": session_id,
            "student_type": getattr(resolved_state, "student_type", None),
            "school_year": getattr(resolved_state, "school_year", None),
            "registration_run": getattr(resolved_state, "registration_run", None),
            "inner_data": getattr(resolved_state, "inner_data", {}) or {},
            "reasoning_steps": self.export_reasoning(),
        }

        # -------------------------------
        # 5) STILL IN FLOW → prompt user
        # -------------------------------
        if not dialog_result.proceed:
            # We are still collecting required slots (documents, school_year,
            # parent info, attended-before flag, file upload, etc.).
            # Just return the prompt and keep the subagent_session_id active.
            if dialog_result.prompt_answer_text:
                logger.info(
                    "[RegisterNewStudentAgent] Prompting user; phase=%s status=%s",
                    dialog_result.prompt_phase,
                    dialog_result.prompt_status,
                )

                return RegistrationAgentResult(
                    answer_text=dialog_result.prompt_answer_text,
                    status="ok",
                    intent="register_new_student",
                    extra_chunks=[],
                    index="main",
                    agent_session_id=session_id,
                    # 🔹 keep the registration dialog active
                    subagent_session_id=session_id,
                    agent_id=ctx.agent_id,
                    agent_name=ctx.agent_name,
                    data={"agent_debug_information": debug_info},
                    children=[],
                )

            # Should be rare: no prompt text but also not allowed to proceed
            fallback_text = (
                "I’m still gathering the details for this registration. "
                "Please clarify or try again."
            )
            logger.warning(
                "[RegisterNewStudentAgent] dialog_result.proceed=False but no prompt; "
                "returning safe fallback message."
            )
            return RegistrationAgentResult(
                answer_text=fallback_text,
                status="pending",
                intent="register_new_student",
                extra_chunks=[],
                index="main",
                agent_session_id=session_id,
                subagent_session_id=session_id,
                agent_id=ctx.agent_id,
                agent_name=ctx.agent_name,
                data={"agent_debug_information": debug_info},
                children=[],
            )

        # -------------------------------
        # 6) FLOW COMPLETE → thank you + handoff
        # -------------------------------
        # At this point, all required dialog slots are filled, including the
        # proof_of_residency_upload. Instead of calling the registration
        # service, we:
        #  - thank the user,
        #  - mark the registration dialog as complete, and
        #  - clear the subagent_session_id so the router goes back to general RAG.
        thank_you = (
            "Thank you! I've received your Proof of Residency document and saved it with "
            "your registration details. You're all set for now.\n\n"
            "If you have any other questions, feel free to ask."
        )

        # Mark session as complete so this flow is no longer treated as active.
        resolved_state.session_mode = None
        await _state_store.save(resolved_state)

        debug_info["registration_run"] = "complete"

        return RegistrationAgentResult(
            answer_text=thank_you,
            status="ok",
            intent="register_new_student",
            extra_chunks=[],
            index="main",
            agent_session_id=session_id,
            # ❌ Explicitly clear the subagent_session_id so the next turn
            # falls back to the general RAG agent instead of this dialog.
            subagent_session_id=None,
            agent_id=ctx.agent_id,
            agent_name=ctx.agent_name,
            data={"agent_debug_information": debug_info},
            children=[],
        )
