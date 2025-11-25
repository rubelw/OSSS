from __future__ import annotations

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

from .registration_client import RegistrationServiceClient
from .registration_dialog import (
    DialogStepResult,
    SessionMode,
    decide_session_mode,
    evaluate_dialog_slots,
)
from .registration_state import (
    InMemoryRegistrationStateStore,
    RegistrationSessionState,
    RegistrationStateStore,
)

from OSSS.ai.agents.reasoning import ReasoningTraceMixin, ReasoningStep


# Dedicated logger for the "agent-level" orchestration logic.
# All high-level flow decisions, external calls, and parsing behaviors
# should be visible through this logger at INFO/DEBUG.
logger = logging.getLogger("OSSS.ai.agents.registration.agent")


@register_agent("register_new_student")
class RegisterNewStudentAgent(ReasoningTraceMixin):
    """
    High-level agent for orchestrating the **student registration** workflow.

    This agent is responsible for:
      - Deciding whether the user is starting a **new** registration session
        or **continuing** an existing one.
      - Managing and updating a per-session registration state, including:
          * `student_type` ("new" vs "existing")
          * `school_year` ("2025-26", etc.)
      - Performing multi-turn **slot filling**:
          * Asking the user clarifying questions when required fields
            are missing or ambiguous.
      - Invoking the external **A2A registration service** via HTTP
        once sufficient information is available.
      - Normalizing the **downstream response** into a standard
        `AgentResult` object for your chat/UI layer.

    Design goals
    ------------
    - Keep side effects (HTTP calls, storage) **outside** the core dialog logic.
      The dialog logic lives in `registration_dialog.py`.
    - Keep persistence concerns **behind an interface** (`RegistrationStateStore`),
      so this agent can be backed by in-memory testing stores, Redis, DB, etc.
    - Make it easy to test by mocking `RegistrationServiceClient` and
      `RegistrationStateStore`.
    """

    # This is the intent name the router/intent classifier can use to
    # identify this agent as the handler for registration flows.
    intent_name = "register_new_student"

    def __init__(
        self,
        state_store: Optional[RegistrationStateStore] = None,
        service_client: Optional[RegistrationServiceClient] = None,
    ) -> None:
        """
        Initialize the registration agent with a state store and HTTP client.

        Notes
        -----
        - Uses an in-memory state store by default (dev/testing).
        - Uses a default A2A base_url of "http://a2a:8086"; override via DI
          in production.
        """
        # Initialize mixin (ReasoningTraceMixin) + any potential future bases.
        super().__init__()

        self.state_store: RegistrationStateStore = (
            state_store or InMemoryRegistrationStateStore()
        )
        self.service_client: RegistrationServiceClient = (
            service_client or RegistrationServiceClient(base_url="http://a2a:8086")
        )

        logger.debug(
            "[RegisterNewStudentAgent.__init__] Initialized with state_store=%s "
            "service_client_base=%s",
            type(self.state_store).__name__,
            getattr(self.service_client, "_base_url", "<unknown>"),
        )

    # ------------------------------------------------------------------
    # Main entrypoint
    # ------------------------------------------------------------------
    async def run(self, ctx: AgentContext) -> AgentResult:
        """
        Primary entrypoint for the registration agent.

        This method:
          1. Decides whether the current turn is *new* vs *continue*,
             and which `session_id` to use.
          2. Loads any existing `RegistrationSessionState` for that session.
          3. Passes the state + context to the **dialog policy** to determine
             whether:
                - we need to PROMPT the user for more info (blocking), or
                - we can PROCEED to call the A2A service.
          4. Calls the A2A registration service if appropriate.
          5. Parses the A2A response and wraps it as an `AgentResult`.

        The return value is always an `AgentResult`, which may represent:
          - A prompt asking the user for missing fields.
          - A final or intermediate answer from the A2A service.
          - An error state if network/JSON parsing fails.
        """
        # New: start a fresh ReAct-style reasoning trace for this turn.
        self.reset_reasoning_trace()

        logger.info(
            "[run] Starting registration flow | query=%r subagent_session_id=%r "
            "agent_id=%r agent_name=%r",
            ctx.query,
            ctx.subagent_session_id,
            ctx.agent_id,
            ctx.agent_name,
        )

        # Router may or may not set agent_id/agent_name on the context. If not,
        # we assign safe defaults to avoid None leaking into the final result.
        agent_id = ctx.agent_id or "registration-agent"
        agent_name = ctx.agent_name or "Registration"

        # --------------------------------------------------------------
        # 1) Decide session mode (Thought → Action → Observation)
        # --------------------------------------------------------------
        step_session_mode: ReasoningStep = self.add_reasoning_step(
            phase="session_mode",
            thought=(
                "Decide whether this turn continues an existing registration "
                "session or starts a new one, based on ctx.subagent_session_id "
                "and simple intent triggers (new vs continue)."
            ),
            action="decide_session_mode(ctx)",
        )

        session_mode, session_id = decide_session_mode(ctx)
        if session_id is None:
            # Defensive: ensure we never propagate a None session_id.
            import uuid

            session_id = str(uuid.uuid4())
            logger.warning(
                "[run] decide_session_mode returned None session_id; generated new=%s",
                session_id,
            )

        self.update_reasoning_observation(
            step_session_mode,
            {
                "session_mode": session_mode,
                "session_id": session_id,
                "existing_subagent_session_id": ctx.subagent_session_id,
            },
        )

        # --------------------------------------------------------------
        # 2) Retrieve existing state (if any) or create a fresh one
        # --------------------------------------------------------------
        step_load_state: ReasoningStep = self.add_reasoning_step(
            phase="load_state",
            thought=(
                "Load any prior RegistrationSessionState for this session_id so we "
                "can continue slot-filling across turns."
            ),
            action="state_store.get(session_id)",
        )

        existing_state = await self.state_store.get(session_id)
        if existing_state is None:
            existing_state = RegistrationSessionState(session_id=session_id)
            found_existing = False
            logger.debug(
                "[run] No prior state found; created new RegistrationSessionState(session_id=%s)",
                session_id,
            )
        else:
            found_existing = True
            logger.debug(
                "[run] Loaded existing RegistrationSessionState for session_id=%s: %s",
                session_id,
                existing_state,
            )

        self.update_reasoning_observation(
            step_load_state,
            {
                "found_existing_state": found_existing,
                "state_repr": repr(existing_state),
            },
        )

        # --------------------------------------------------------------
        # 3) Run dialog policy (slot filling)
        # --------------------------------------------------------------
        step_dialog: ReasoningStep = self.add_reasoning_step(
            phase="dialog_policy",
            thought=(
                "Given the current session_mode and session_state, decide whether "
                "we have enough information to call the registration service, or "
                "whether we must prompt the user for missing fields."
            ),
            action="evaluate_dialog_slots(...)",
        )

        dialog_result = await evaluate_dialog_slots(
            ctx=ctx,
            session_mode=session_mode,
            session_state=existing_state,
            state_store=self.state_store,
        )

        self.update_reasoning_observation(
            step_dialog,
            {
                "proceed": dialog_result.proceed,
                "prompt_phase": dialog_result.prompt_phase,
                "prompt_status": dialog_result.prompt_status,
                "has_prompt": dialog_result.prompt_answer_text is not None,
            },
        )

        # 3a) If the dialog engine says "we need to ask the user something",
        #     we immediately return a prompt-style AgentResult and DO NOT
        #     call the A2A service yet.
        if dialog_result.prompt_answer_text is not None:
            logger.info(
                "[run] Dialog policy requires prompt phase=%s status=%s; "
                "returning prompt result.",
                dialog_result.prompt_phase,
                dialog_result.prompt_status,
            )
            prompt_result = self._make_prompt_result(
                ctx=ctx,
                agent_id=agent_id,
                agent_name=agent_name,
                session_id=session_id,
                dialog=dialog_result,
                session_mode=session_mode,
            )
            # Attach full reasoning trace for introspection in the UI/logs.
            self.attach_reasoning_to_agent_result(prompt_result)
            return prompt_result

        # At this point, dialog_result indicates we can proceed to call A2A.
        state = dialog_result.session_state or existing_state

        # --------------------------------------------------------------
        # 4) Call the external A2A registration service
        # --------------------------------------------------------------
        step_http: ReasoningStep = self.add_reasoning_step(
            phase="http_call",
            thought=(
                "We have sufficient dialog info. Build the payload and POST it to "
                "the A2A /admin/registration endpoint."
            ),
            action="service_client.register(payload)",
        )

        # This is the integration boundary: we translate our internal state
        # and context into a JSON payload for the external service.
        payload = self._build_action_payload(ctx, agent_id, agent_name, state)
        logger.debug("[run] Final A2A payload: %s", payload)

        try:
            # service_client wraps an httpx.AsyncClient and will raise
            # httpx.HTTPError on network issues or non-2xx responses.
            response = await self.service_client.register(payload)
            self.update_reasoning_observation(
                step_http,
                {
                    "status_code": response.status_code,
                    "ok": response.status_code < 400,
                },
            )
        except httpx.HTTPError as e:
            # Covers both "pure" network errors and HTTPStatusError (4xx/5xx).
            # We do not attempt to recover here; instead we return an error
            # result with a user-friendly message and detailed debug info.
            logger.error("Registration HTTP error: %s", e, exc_info=True)
            self.update_reasoning_observation(
                step_http,
                {"error": "http_error", "details": str(e)},
            )
            error_result = self._make_error_result(
                ctx=ctx,
                agent_id=agent_id,
                agent_name=agent_name,
                session_id=None,  # No valid response -> no server-side session id
                session_mode=session_mode,
                existing_session_id=ctx.subagent_session_id,
                student_type=state.student_type,
                school_year=state.school_year,
                phase="http_error",
                message=(
                    "Registration failed while contacting the registration service. "
                    "Please try again or contact support."
                ),
                reason="http_error",
                inner_data={"error": "http_error", "details": str(e)},
            )
            self.attach_reasoning_to_agent_result(error_result)
            return error_result

        # --------------------------------------------------------------
        # 4b) Parse JSON body
        # --------------------------------------------------------------
        step_parse_json: ReasoningStep = self.add_reasoning_step(
            phase="parse_response",
            thought=(
                "Parse JSON from A2A and unwrap registration_run into answer_text "
                "and metadata."
            ),
            action="response.json() + _parse_a2a_response(...)",
        )

        # At this point we have a successful HTTP response. The next failure
        # condition is malformed or unexpected JSON.
        try:
            raw = response.json()
        except ValueError as e:
            # JSON parsing failure: log the raw response body (truncated) for
            # later inspection and return a structured error result.
            logger.error(
                "[run] Failed to parse A2A JSON response: %s body=%r",
                e,
                response.text[:2000],
            )
            self.update_reasoning_observation(
                step_parse_json,
                {
                    "error": "json_parse_error",
                    "body_preview": response.text[:2000],
                },
            )
            error_result = self._make_error_result(
                ctx=ctx,
                agent_id=agent_id,
                agent_name=agent_name,
                session_id=session_id,
                session_mode=session_mode,
                existing_session_id=ctx.subagent_session_id,
                student_type=state.student_type,
                school_year=state.school_year,
                phase="json_parse_error",
                message=(
                    "The registration service returned an invalid response. "
                    "Please try again later or contact support."
                ),
                reason="json_parse_error",
                inner_data={
                    "error": "json_parse_error",
                    "body": response.text[:2000],
                },
            )
            self.attach_reasoning_to_agent_result(error_result)
            return error_result

        logger.info("[run] Registration raw result from A2A: %s", raw)

        # --------------------------------------------------------------
        # 5) Parse A2A payload into answer text + metadata
        # --------------------------------------------------------------
        # We now transform the arbitrary shape of A2A's JSON into a standardized
        # form: (answer_text, intent, agent_id, agent_name, session_id, etc.).
        (
            answer_text,
            final_intent,
            final_agent_id,
            final_agent_name,
            final_session_id,
            registration_run,
            inner_data,
        ) = self._parse_a2a_response(
            raw,
            fallback_intent=self.intent_name,
            fallback_agent_id=agent_id,
            fallback_agent_name=agent_name,
            fallback_session_id=session_id,
        )

        self.update_reasoning_observation(
            step_parse_json,
            {
                "final_intent": final_intent,
                "final_agent_id": final_agent_id,
                "final_agent_name": final_agent_name,
                "final_session_id": final_session_id,
                "status": registration_run.get("status", "ok"),
            },
        )

        # Optional prefix describing whether we started a new or continued
        # an existing registration, mirroring the original behavior.
        # This gives the user a clear mental model for what just happened.
        answer_text = self._prefix_with_session_info(
            answer_text=answer_text,
            session_mode=session_mode,
            session_id=final_session_id,
            had_existing_session=ctx.subagent_session_id is not None,
        )

        # Debug chunk for Sources UI: treat the registration_run as a "source"
        # so downstream UIs can display "where did this answer come from?".
        debug_neighbors = [
            {
                "score": 1.0,
                "filename": "registration_run",
                "chunk_index": None,
                "text_preview": str(answer_text)[:800],
                "image_paths": None,
                "page_index": None,
                "page_chunk_index": None,
            }
        ]

        # --------------------------------------------------------------
        # 6) Persist final values (state) and build final AgentResult
        # --------------------------------------------------------------
        # We update the stored state for this final_session_id so it reflects
        # the most recent student_type and school_year used during this turn.
        await self.state_store.upsert(
            RegistrationSessionState(
                session_id=final_session_id,
                student_type=state.student_type,
                school_year=state.school_year,
            )
        )

        logger.info(
            "[run] Finalizing registration AgentResult | session_id=%s status=%s "
            "intent=%r student_type=%r school_year=%r",
            final_session_id,
            registration_run.get("status", "ok"),
            final_intent,
            state.student_type,
            state.school_year,
        )

        # Final ReAct-style summary step for this turn.
        step_finalize: ReasoningStep = self.add_reasoning_step(
            phase="finalize",
            thought=(
                "Persist final registration state and construct the AgentResult "
                "returned to the router/UI."
            ),
            action="state_store.upsert(...) + build AgentResult",
            observation={
                "session_mode": session_mode,
                "final_session_id": final_session_id,
                "student_type": state.student_type,
                "school_year": state.school_year,
            },
        )

        # agent_debug_information is the "single pane of glass" for understanding
        # what this agent saw and decided at this turn.
        debug_payload = {
            "phase": "final",
            "query": ctx.query,
            "session_mode": session_mode,
            "existing_registration_session_id": ctx.subagent_session_id,
            "registration_session_id": final_session_id,
            "student_type": state.student_type,
            "school_year": state.school_year,
            "registration_run": registration_run,
            "inner_data": inner_data,
        }

        result = AgentResult(
            answer_text=answer_text,
            intent=final_intent or self.intent_name,
            index="registration",
            agent_id=final_agent_id,
            agent_name=final_agent_name,
            extra_chunks=debug_neighbors,
            status=registration_run.get("status", "ok"),
            agent_session_id=final_session_id,
            data={
                "registration_run": registration_run,
                "inner_data": inner_data,
                "student_type": state.student_type,
                "school_year": state.school_year,
                "agent_debug_information": debug_payload,
            },
        )

        # Attach full reasoning trace into agent_debug_information["reasoning_steps"].
        self.attach_reasoning_to_agent_result(result)
        return result

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _make_prompt_result(
        self,
        *,
        ctx: AgentContext,
        agent_id: str,
        agent_name: str,
        session_id: str,
        dialog: DialogStepResult,
        session_mode: Optional[SessionMode],
    ) -> AgentResult:
        """
        Construct an `AgentResult` representing a **prompt** back to the user.

        This is used when the dialog policy indicates we are missing critical
        information (e.g., "new vs existing student", or school year) and must
        ask the user a question before proceeding.
        """
        # Compact debug snapshot for this specific prompt phase.
        debug_payload = {
            "phase": dialog.prompt_phase,
            "query": ctx.query,
            "session_mode": session_mode,
            "existing_registration_session_id": ctx.subagent_session_id,
            "registration_session_id": session_id,
            "student_type": None,
            "school_year": None,
            "registration_run": None,
            "inner_data": {},
        }

        logger.debug(
            "[_make_prompt_result] phase=%s status=%s session_id=%s",
            dialog.prompt_phase,
            dialog.prompt_status,
            session_id,
        )

        # Status is usually "needs_student_type", "needs_school_year", etc.
        return AgentResult(
            answer_text=dialog.prompt_answer_text or "",
            intent=self.intent_name,
            index="registration",
            agent_id=agent_id,
            agent_name=agent_name,
            extra_chunks=[],
            status=dialog.prompt_status or "needs_input",
            agent_session_id=session_id,
            data={
                "reason": dialog.prompt_reason,
                "phase": dialog.prompt_phase,
                "session_mode": session_mode,
                "agent_debug_information": debug_payload,
            },
        )

    def _make_error_result(
        self,
        *,
        ctx: AgentContext,
        agent_id: str,
        agent_name: str,
        session_id: Optional[str],
        session_mode: Optional[SessionMode],
        existing_session_id: Optional[str],
        student_type: Optional[str],
        school_year: Optional[str],
        phase: str,
        message: str,
        reason: str,
        inner_data: Dict[str, Any],
    ) -> AgentResult:
        """
        Construct an `AgentResult` representing an error state.

        Used for:
          - HTTP/network errors (e.g., timeout, connection refused)
          - JSON parsing errors
          - Other non-recoverable issues contacting A2A.

        The error information is captured in `data` for debugging,
        and a user-friendly message is returned in `answer_text`.
        """
        debug_payload = {
            "phase": phase,
            "query": ctx.query,
            "session_mode": session_mode,
            "existing_registration_session_id": existing_session_id,
            "registration_session_id": session_id,
            "student_type": student_type,
            "school_year": school_year,
            "registration_run": None,
            "inner_data": inner_data,
        }

        logger.debug(
            "[_make_error_result] phase=%s session_id=%s reason=%s",
            phase,
            session_id,
            reason,
        )

        return AgentResult(
            answer_text=message,
            intent=self.intent_name,
            index="registration",
            agent_id=agent_id,
            agent_name=agent_name,
            extra_chunks=[],
            status="error",
            agent_session_id=session_id,
            data={
                "reason": reason,
                "inner_data": inner_data,
                "student_type": student_type,
                "school_year": school_year,
                "agent_debug_information": debug_payload,
            },
        )

    def _build_action_payload(
        self,
        ctx: AgentContext,
        agent_id: str,
        agent_name: str,
        state: RegistrationSessionState,
    ) -> Dict[str, Any]:
        """
        Build the JSON payload sent to the A2A registration service.
        """
        # Base fields that are always sent to A2A.
        payload: Dict[str, Any] = {
            "query": ctx.query,
            "registration_agent_id": "registration-agent",
            "registration_skill": "registration",
            "agent_session_id": state.session_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
        }

        # Only include optional fields if we have them, to avoid sending
        # noisy nulls/empty values and to preserve a clean contract.
        if state.student_type:
            payload["student_type"] = state.student_type
        if state.school_year:
            payload["school_year"] = state.school_year

        return payload

    def _parse_a2a_response(
        self,
        raw: Dict[str, Any],
        *,
        fallback_intent: str,
        fallback_agent_id: str,
        fallback_agent_name: str,
        fallback_session_id: str,
    ) -> Tuple[str, str, str, str, str, Dict[str, Any], Dict[str, Any]]:
        """
        Parse the A2A service response into structured fields.
        """
        # A2A is expected to wrap useful information into a `registration_run`
        # field, but we never trust its presence blindly; hence the `or {}`.
        registration_run: Dict[str, Any] = raw.get("registration_run", {}) or {}
        logger.debug(
            "[_parse_a2a_response] registration_run=%s",
            registration_run,
        )

        inner_payload: Optional[Dict[str, Any]] = None

        # Prefer a structured "answer" object if it exists
        if isinstance(registration_run.get("answer"), dict):
            inner_payload = registration_run["answer"]
            logger.debug(
                "[_parse_a2a_response] Using registration_run['answer'] as inner_payload."
            )
        else:
            op = registration_run.get("output_preview")
            logger.debug(
                "[_parse_a2a_response] registration_run['answer'] not dict; output_preview=%r",
                op,
            )
            if isinstance(op, dict):
                # Some flows may put the structured payload in output_preview
                inner_payload = op
                logger.debug(
                    "[_parse_a2a_response] Using dict output_preview as inner_payload."
                )
            elif isinstance(op, str):
                # Sometimes the A2A service returns a stringified dict. We
                # attempt to parse it via ast.literal_eval as a best effort,
                # knowing that malformed strings will simply cause a warning.
                try:
                    maybe = ast.literal_eval(op)
                    if isinstance(maybe, dict):
                        inner_payload = maybe
                        logger.debug(
                            "[_parse_a2a_response] Parsed output_preview string into dict inner_payload."
                        )
                except Exception as e:
                    logger.warning(
                        "[_parse_a2a_response] Failed to parse output_preview as dict: %s op=%r",
                        e,
                        op[:200],
                    )

        # Initialize with sensible fallbacks. If parsing fails or fields are
        # missing, these fallback values protect the rest of the pipeline.
        registration_answer_text = "No details available."
        registration_intent = fallback_intent
        registration_agent_id = fallback_agent_id
        registration_agent_name = fallback_agent_name
        registration_session_id = fallback_session_id
        inner_data: Dict[str, Any] = {}

        if isinstance(inner_payload, dict):
            # This is the most structured path: we have a dict with potential
            # keys like "answer", "intent", "agent_id", etc.
            inner_data = inner_payload
            logger.debug(
                "[_parse_a2a_response] inner_payload dict=%s",
                inner_payload,
            )

            # Prefer "answer", then "message", else keep the default text.
            registration_answer_text = (
                inner_payload.get("answer")
                or inner_payload.get("message")
                or "No details available."
            )

            registration_intent = inner_payload.get(
                "intent",
                registration_run.get("intent", fallback_intent),
            )

            registration_agent_id = (
                inner_payload.get("agent_id")
                or registration_run.get("agent_id")
                or fallback_agent_id
            )

            registration_agent_name = (
                inner_payload.get("agent_name")
                or registration_run.get("agent_name")
                or fallback_agent_name
            )

            registration_session_id = (
                inner_payload.get("agent_session_id")
                or registration_run.get("agent_session_id")
                or fallback_session_id
            )
        else:
            # Less structured path: treat output_preview as the answer text
            # and read as many fields as we can from registration_run.
            op = registration_run.get("output_preview") or "No details available."
            registration_answer_text = str(op)

            registration_intent = registration_run.get(
                "intent",
                fallback_intent,
            )

            registration_agent_id = registration_run.get("agent_id") or fallback_agent_id
            registration_agent_name = (
                registration_run.get("agent_name") or fallback_agent_name
            )
            registration_session_id = (
                registration_run.get("agent_session_id") or fallback_session_id
            )

        logger.debug(
            "[_parse_a2a_response] After primary parse | answer_text=%r intent=%r "
            "agent_id=%r agent_name=%r session_id=%r",
            registration_answer_text,
            registration_intent,
            registration_agent_id,
            registration_agent_name,
            registration_session_id,
        )

        # Final normalization: sometimes answer_text is itself a stringified dict
        # that contains an "answer" key; we try to unwrap that. This provides
        # extra robustness if A2A double-wraps the payload.
        if isinstance(registration_answer_text, str):
            stripped = registration_answer_text.strip()
            if stripped.startswith("{") and (
                "'answer'" in stripped or '"answer"' in stripped
            ):
                logger.debug(
                    "[_parse_a2a_response] Attempting to normalize answer_text that "
                    "looks like a dict: %r",
                    stripped[:200],
                )
                try:
                    maybe_dict = ast.literal_eval(stripped)
                    if isinstance(maybe_dict, dict) and "answer" in maybe_dict:
                        registration_answer_text = maybe_dict["answer"]
                        logger.debug(
                            "[_parse_a2a_response] Normalized registration_answer_text "
                            "from dict wrapper."
                        )
                except Exception as e:
                    logger.warning(
                        "[_parse_a2a_response] Failed to normalize registration_answer_text "
                        "as dict: %s text=%r",
                        e,
                        stripped[:200],
                    )

        return (
            registration_answer_text,
            registration_intent,
            registration_agent_id,
            registration_agent_name,
            registration_session_id,
            registration_run,
            inner_data,
        )

    def _prefix_with_session_info(
        self,
        *,
        answer_text: str,
        session_mode: Optional[SessionMode],
        session_id: str,
        had_existing_session: bool,
    ) -> str:
        """
        Prefix the final answer text with a short explanation of the
        session mode (new vs continue) and the session ID.

        This mirrors the original behavior and provides the user with:
          - Confirmation that a new registration was started OR
          - Confirmation that an existing registration was continued
          - The explicit registration session ID for reference.
        """
        prefix_lines: List[str] = []

        if session_mode == "new":
            # Distinguish between "first-ever registration" and "new registration
            # while another is already in progress" to give the user better context.
            if had_existing_session:
                prefix_lines.append(
                    "Okay, I’ve started a new registration for a different student."
                )
            else:
                prefix_lines.append("Okay, I’ve started a new registration.")
            prefix_lines.append(f"Registration session ID: {session_id}")
        elif session_mode == "continue":
            prefix_lines.append("Okay, continuing your existing registration.")
            prefix_lines.append(f"Registration session ID: {session_id}")

        if not prefix_lines:
            # If we don't recognize the session_mode (or it's None), we don't
            # add a prefix and simply return the original text.
            return answer_text

        logger.debug(
            "[_prefix_with_session_info] Adding prefix lines=%r for session_mode=%r",
            prefix_lines,
            session_mode,
        )

        # Separate prefix and answer with blank lines for a clean markdown-ish
        # reading experience in chat UIs.
        return "\n\n".join(prefix_lines) + "\n\n" + str(answer_text)
