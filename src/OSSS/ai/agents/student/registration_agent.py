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
      - Optionally calls the RegistrationServiceClient.
      - Returns a RegistrationAgentResult with debug trace for the UI.
    """

    def __init__(self) -> None:
        # Keep a per-call reasoning trace (reset on each run)
        self._reasoning_steps: List[ReasoningStep] = []

    # ------------------------------------------------------------------
    # Reasoning helpers (fixes the missing reset_reasoning)
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
            session_id = (
                ctx.subagent_session_id
                or ctx.session_id
            )

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
                "we have enough information to call the registration service, or "
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

        # -------------------------------
        # 4) Build debug info blob
        # -------------------------------
        debug_info: dict[str, Any] = {
            "phase": dialog_result.prompt_phase or (
                "proceed" if dialog_result.proceed else "unknown"
            ),
            "query": ctx.query,
            "session_mode": session_mode,
            "existing_registration_session_id": ctx.subagent_session_id,
            "registration_session_id": session_id,
            "student_type": getattr(resolved_state, "student_type", None),
            "school_year": getattr(resolved_state, "school_year", None),
            "registration_run": None,
            "inner_data": {},
            "reasoning_steps": self.export_reasoning(),
        }

        # -------------------------------
        # 5) If we must prompt the user, do so now (no A2A call)
        # -------------------------------
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
                agent_id=ctx.agent_id,
                agent_name=ctx.agent_name,
                data={"agent_debug_information": debug_info},
                children=[],
            )

        # If we got here without permission to proceed, just bail gracefully.
        if not dialog_result.proceed:
            fallback_text = (
                "I’m still gathering the details for this registration. "
                "Please clarify whether you’re registering a new or existing student, "
                "and for which school year."
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
                agent_id=ctx.agent_id,
                agent_name=ctx.agent_name,
                data={"agent_debug_information": debug_info},
                children=[],
            )

        # -------------------------------
        # 6) We have enough info: call registration service
        # -------------------------------
        self.append_reasoning_step(
            phase="call_service",
            thought="Call the registration back-end with the resolved session_state.",
            action="registration_client.submit_registration(session_state)",
            observation=None,
        )

        try:
            # Keep the signature here minimal & generic so it works with your
            # RegistrationServiceClient implementation.
            service_response = await _registration_client.submit_registration(
                resolved_state
            )
            self.update_last_observation(
                {
                    "service_call": "ok",
                    "service_response_preview": repr(service_response)[:500],
                }
            )
        except Exception as e:
            logger.exception(
                "[RegisterNewStudentAgent] Error calling registration service"
            )
            self.update_last_observation(
                {
                    "service_call": "error",
                    "error": str(e),
                }
            )
            debug_info["registration_run"] = "error"

            error_text = (
                "I tried to start the registration, but there was a problem "
                "contacting the registration system. Please try again in a few "
                "minutes or contact the school office."
            )
            return RegistrationAgentResult(
                answer_text=error_text,
                status="error",
                intent="register_new_student",
                extra_chunks=[],
                index="main",
                agent_session_id=session_id,
                agent_id=ctx.agent_id,
                agent_name=ctx.agent_name,
                data={"agent_debug_information": debug_info},
                children=[],
            )

        # -------------------------------
        # 7) Success path
        # -------------------------------
        debug_info["registration_run"] = "success"

        student_label = resolved_state.student_type or "student"
        year_label = (
            f" for **{resolved_state.school_year}**"
            if resolved_state.school_year
            else ""
        )

        success_text = (
            f"I’ve started the online registration for a **{student_label}**{year_label}.\n\n"
            "You’ll receive a follow-up from the Dallas Center-Grimes registration system "
            "with a link or next steps to complete the process. If you don’t see it within "
            "a few minutes, please check your spam folder or contact the school office."
        )

        return RegistrationAgentResult(
            answer_text=success_text,
            status="ok",
            intent="register_new_student",
            extra_chunks=[],
            index="main",
            agent_session_id=session_id,
            agent_id=ctx.agent_id,
            agent_name=ctx.agent_name,
            data={
                "agent_debug_information": debug_info,
                "registration_response": repr(service_response)[:2000],
            },
            children=[],
        )
