from __future__ import annotations

import ast
import json
import logging
import uuid
from typing import Optional, Dict, Any

import re
import requests

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

logger = logging.getLogger("OSSS.ai.agents.registration")


# ----------------------------------------------------------------------
# Simple in-process store for registration session state.
# In production, back this with Redis or OSSS.sessions instead.
# ----------------------------------------------------------------------
_REGISTRATION_STATE: dict[str, dict[str, Optional[str]]] = {}


def _get_registration_state(session_id: Optional[str]) -> dict[str, Optional[str]]:
    if not session_id:
        return {}
    return _REGISTRATION_STATE.get(session_id, {}).copy()


def _set_registration_state(
    session_id: Optional[str],
    *,
    student_type: Optional[str] = None,
    school_year: Optional[str] = None,
) -> None:
    if not session_id:
        return
    state = _REGISTRATION_STATE.setdefault(session_id, {})
    if student_type is not None:
        state["student_type"] = student_type
    if school_year is not None:
        state["school_year"] = school_year


@register_agent("register_new_student")
class RegisterNewStudentAgent:
    """
    Agent that orchestrates student registration via the A2A registration service.

    It supports:
      - Starting a NEW registration session
      - CONTINUING an existing registration session (subagent_session_id)
      - Prompting the user to choose between new vs continue when appropriate
      - For NEW sessions, prompting for:
          * New vs existing student
          * School year (e.g., 2025-26)
          * Parent/guardian contact info
    """

    intent_name = "register_new_student"
    registration_url = "http://a2a:8086/admin/registration"

    # ------------------------------------------------------------------
    # Generic trigger helper
    # ------------------------------------------------------------------
    @staticmethod
    def _has_trigger(query: str, triggers: list[str]) -> bool:
        q = (query or "").lower()
        return any(t in q for t in triggers)

    # ------------------------------------------------------------------
    # Helpers to interpret the user query when an existing session exists
    # ------------------------------------------------------------------
    @classmethod
    def _wants_new_registration(cls, query: str) -> bool:
        return cls._has_trigger(
            query,
            [
                "start a new registration",
                "start another registration",
                "another registration",
                "new registration",
                "register another student",
                "register a different student",
            ],
        )

    @classmethod
    def _wants_continue_registration(cls, query: str) -> bool:
        return cls._has_trigger(
            query,
            [
                "continue",
                "resume",
                "pick up where we left off",
                "continue current registration",
                "resume registration",
                "same registration",
                "same student",
            ],
        )

    # ------------------------------------------------------------------
    # Helpers for student type and school year
    # ------------------------------------------------------------------
    @classmethod
    def _wants_new_student(cls, query: str) -> bool:
        return cls._has_trigger(
            query,
            [
                "new student",
                "register a new student",
                "register new student",
                "brand new student",
            ],
        )

    @classmethod
    def _wants_existing_student(cls, query: str) -> bool:
        return cls._has_trigger(
            query,
            [
                "existing student",
                "previously enrolled",
                "returning student",
                "student who attended before",
                "attended dc-g in the past",
                "attended dc-g schools in the past",
            ],
        )

    @staticmethod
    def _extract_school_year(query: str) -> Optional[str]:
        """
        Try to extract a school year from free text like:
          - "2025-26"
          - "2025/26"
          - "2025–26" (en dash)
        Returns the matched string, or None.
        """
        if not query:
            return None

        q = query.strip()
        # Normalize fancy dashes to '-'
        q_norm = q.replace("–", "-").replace("—", "-")

        # Pattern: 20xx-2x or 20xx-20xx or with slash
        m = re.search(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})", q_norm)
        if m:
            return m.group(0)
        return None

    # ------------------------------------------------------------------
    # Debug payload + AgentResult helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_debug_payload(
        *,
        phase: str,
        ctx: AgentContext,
        session_mode: Optional[str],
        existing_registration_session_id: Optional[str],
        registration_session_id: Optional[str],
        student_type: Optional[str],
        school_year: Optional[str],
        registration_run: Optional[Dict[str, Any]] = None,
        inner_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "phase": phase,
            "query": ctx.query,
            "session_mode": session_mode,
            "existing_registration_session_id": existing_registration_session_id,
            "registration_session_id": registration_session_id,
            "student_type": student_type,
            "school_year": school_year,
            "registration_run": registration_run,
            "inner_data": inner_data or {},
        }

    def _make_result(
        self,
        *,
        ctx: AgentContext,
        phase: str,
        answer_text: str,
        status: str,
        agent_id: str,
        agent_name: str,
        registration_session_id: Optional[str],
        session_mode: Optional[str],
        existing_registration_session_id: Optional[str],
        student_type: Optional[str],
        school_year: Optional[str],
        reason: Optional[str] = None,
        inner_data: Optional[Dict[str, Any]] = None,
        registration_run: Optional[Dict[str, Any]] = None,
        extra_chunks: Optional[list[dict]] = None,
    ) -> AgentResult:
        """
        Centralized place to build AgentResult + agent_debug_information.
        """
        debug_payload = self._build_debug_payload(
            phase=phase,
            ctx=ctx,
            session_mode=session_mode,
            existing_registration_session_id=existing_registration_session_id,
            registration_session_id=registration_session_id,
            student_type=student_type,
            school_year=school_year,
            registration_run=registration_run,
            inner_data=inner_data,
        )

        data: Dict[str, Any] = {
            "agent_debug_information": debug_payload,
        }
        if reason:
            data["reason"] = reason
        if inner_data is not None:
            data["inner_data"] = inner_data
        if registration_run is not None:
            data["registration_run"] = registration_run
        if student_type is not None:
            data["student_type"] = student_type
        if school_year is not None:
            data["school_year"] = school_year

        return AgentResult(
            answer_text=answer_text,
            intent="register_new_student",
            index="registration",
            agent_id=agent_id,
            agent_name=agent_name,
            extra_chunks=extra_chunks or [],
            status=status,
            agent_session_id=registration_session_id,
            data=data,
        )

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------
    async def run(self, ctx: AgentContext) -> AgentResult:
        """
        Call the registration service and normalize its response into an AgentResult.
        """
        logger.info("Processing registration for new student with query: %s", ctx.query)

        agent_id = ctx.agent_id or "registration-agent"
        agent_name = ctx.agent_name or "Registration"

        existing_registration_session_id: Optional[str] = ctx.subagent_session_id
        session_mode: Optional[str] = None  # "new" | "continue" | None

        # We'll track these across branches
        student_type: Optional[str] = None
        school_year: Optional[str] = None

        # --------------------------------------------------------------
        # 1) If we already have a registration session, interpret query
        # --------------------------------------------------------------
        if existing_registration_session_id:
            wants_new = self._wants_new_registration(ctx.query)
            wants_continue = self._wants_continue_registration(ctx.query)

            logger.info(
                "Existing registration session=%s; wants_new=%s wants_continue=%s",
                existing_registration_session_id,
                wants_new,
                wants_continue,
            )

            # If user explicitly said "continue" -> reuse existing session id
            if wants_continue and not wants_new:
                registration_session_id = existing_registration_session_id
                session_mode = "continue"
                logger.info(
                    "User chose to CONTINUE registration session %s",
                    registration_session_id,
                )

            # If user explicitly said "new" -> start a new registration
            elif wants_new and not wants_continue:
                registration_session_id = str(uuid.uuid4())
                session_mode = "new"
                logger.info(
                    "User chose to START NEW registration session %s (previous=%s)",
                    registration_session_id,
                    existing_registration_session_id,
                )

            # Ambiguous: user did not say clearly; PROMPT THEM and DO NOT call A2A
            else:
                prompt_text = (
                    f"You already have a registration in progress.\n\n"
                    f"Existing registration session ID: **{existing_registration_session_id}**\n\n"
                    "Would you like to:\n"
                    "- **Continue** this registration, or\n"
                    "- **Start a new registration** for a different student?\n\n"
                    "Please reply with one of these phrases:\n"
                    "- \"continue current registration\"\n"
                    "- \"start a new registration\""
                )

                logger.info(
                    "Existing registration session detected (%s); prompting user to choose "
                    "continue vs new.",
                    existing_registration_session_id,
                )

                return self._make_result(
                    ctx=ctx,
                    phase="prompt_for_continue_or_new",
                    answer_text=prompt_text,
                    status="needs_choice",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    registration_session_id=existing_registration_session_id,
                    session_mode=session_mode,
                    existing_registration_session_id=existing_registration_session_id,
                    student_type=student_type,
                    school_year=school_year,
                    reason="prompt_for_continue_or_new",
                )
        else:
            # No existing subagent session: we are clearly starting new
            registration_session_id = str(uuid.uuid4())
            session_mode = "new"
            logger.info(
                "No existing registration session; starting NEW session %s",
                registration_session_id,
            )

        # If we fell out of the branch above with an existing session, and the
        # user explicitly chose NEW or CONTINUE, registration_session_id is set.
        registration_session_id = locals().get("registration_session_id") or str(
            uuid.uuid4()
        )

        # --------------------------------------------------------------
        # 1b) For NEW sessions, collect student-type + year + parent info
        # --------------------------------------------------------------
        if session_mode == "new":
            # 1b-i: New vs existing student
            wants_new_student = self._wants_new_student(ctx.query)
            wants_existing_student = self._wants_existing_student(ctx.query)

            if not wants_new_student and not wants_existing_student:
                prompt = (
                    "Before we begin the registration process, please confirm:\n\n"
                    "**Is this registration for a:**\n"
                    "- **NEW student**, or\n"
                    "- **EXISTING student** (previously enrolled)?\n\n"
                    "Please reply with:\n"
                    "- \"new student\"\n"
                    "- \"existing student\""
                )

                return self._make_result(
                    ctx=ctx,
                    phase="prompt_for_student_type",
                    answer_text=prompt,
                    status="needs_student_type",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    registration_session_id=registration_session_id,
                    session_mode=session_mode,
                    existing_registration_session_id=existing_registration_session_id,
                    student_type=student_type,
                    school_year=school_year,
                    reason="prompt_for_student_type",
                )

            student_type = "new" if wants_new_student else "existing"
            logger.info("Student type determined: %s", student_type)

            # Persist the determined student_type in the registration session state
            _set_registration_state(
                registration_session_id,
                student_type=student_type,
                school_year=school_year,
            )

            # 1b-ii: If NEW student, require school year
            if student_type == "new":
                school_year = self._extract_school_year(ctx.query)

                if not school_year:
                    prompt = (
                        "Great — you're registering a **new student**.\n\n"
                        "**What school year are you registering for?**\n"
                        "For example:\n"
                        "- \"2024-25\"\n"
                        "- \"2025-26\"\n"
                        "- \"2026-27\""
                    )

                    return self._make_result(
                        ctx=ctx,
                        phase="prompt_for_school_year",
                        answer_text=prompt,
                        status="needs_school_year",
                        agent_id=agent_id,
                        agent_name=agent_name,
                        registration_session_id=registration_session_id,
                        session_mode=session_mode,
                        existing_registration_session_id=existing_registration_session_id,
                        student_type=student_type,
                        school_year=school_year,
                        reason="prompt_for_school_year",
                    )

                logger.info("Captured school_year=%s", school_year)

                # Update stored state now that we know the year
                _set_registration_state(
                    registration_session_id,
                    student_type=student_type,
                    school_year=school_year,
                )

                # 1b-iii: After year is known, prompt for parent info
                prompt_parent = (
                    "Please complete the information below to begin the registration process.\n\n"
                    f"Registration Year\n{school_year}\n\n"
                    "Parent/Guardian First Name\n"
                    "Parent/Guardian Last Name\n"
                    "Parent/Guardian Email Address\n"
                    "Verify Email Address\n"
                    "Has any student you are registering attended DC-G Schools in the past?"
                )

                return self._make_result(
                    ctx=ctx,
                    phase="prompt_for_parent_info",
                    answer_text=prompt_parent,
                    status="needs_parent_info",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    registration_session_id=registration_session_id,
                    session_mode=session_mode,
                    existing_registration_session_id=existing_registration_session_id,
                    student_type=student_type,
                    school_year=school_year,
                    reason="prompt_for_parent_info",
                )
        else:
            # ----------------------------------------------------------
            # LOAD ANY PREVIOUSLY STORED STATE FOR THIS REGISTRATION SESSION
            # ----------------------------------------------------------
            prior_state = _get_registration_state(registration_session_id)
            if prior_state:
                logger.info(
                    "Loaded prior registration state for %s: %s",
                    registration_session_id,
                    prior_state,
                )
                if student_type is None and prior_state.get("student_type") is not None:
                    student_type = prior_state["student_type"]
                if school_year is None and prior_state.get("school_year") is not None:
                    school_year = prior_state["school_year"]

        # --------------------------------------------------------------
        # 1c) For CONTINUE sessions, best-effort parse type/year too
        # --------------------------------------------------------------
        if session_mode == "continue":
            if not student_type:
                if self._wants_new_student(ctx.query):
                    student_type = "new"
                elif self._wants_existing_student(ctx.query):
                    student_type = "existing"

            if not school_year:
                school_year = self._extract_school_year(ctx.query)

            logger.info(
                "Continue mode: inferred student_type=%r school_year=%r from query=%r",
                student_type,
                school_year,
                ctx.query,
            )

            _set_registration_state(
                registration_session_id,
                student_type=student_type,
                school_year=school_year,
            )

        # --------------------------------------------------------------
        # 2) Build payload for A2A registration service
        # --------------------------------------------------------------
        action_data: Dict[str, Any] = {
            "query": ctx.query,
            "registration_agent_id": "registration-agent",
            "registration_skill": "registration",
            "agent_session_id": registration_session_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
        }

        if student_type:
            action_data["student_type"] = student_type
        if school_year:
            action_data["school_year"] = school_year

        # --- HTTP call -------------------------------------------------
        try:
            response = requests.post(
                self.registration_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(action_data),
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            logger.error("Network error during registration: %s", e)

            return self._make_result(
                ctx=ctx,
                phase="http_network_error",
                answer_text=(
                    "There was a network error while trying to process registration. "
                    "Please try again shortly."
                ),
                status="error",
                agent_id=agent_id,
                agent_name=agent_name,
                registration_session_id=None,
                session_mode=session_mode,
                existing_registration_session_id=existing_registration_session_id,
                student_type=student_type,
                school_year=school_year,
                reason="network_error",
                inner_data={"error": "network_error", "details": str(e)},
            )

        if response.status_code != 200:
            logger.error(
                "Failed to register student: HTTP %s %s",
                response.status_code,
                response.text,
            )

            return self._make_result(
                ctx=ctx,
                phase="http_error",
                answer_text=(
                    "Registration failed while contacting the registration service. "
                    "Please try again or contact support."
                ),
                status="error",
                agent_id=agent_id,
                agent_name=agent_name,
                registration_session_id=None,
                session_mode=session_mode,
                existing_registration_session_id=existing_registration_session_id,
                student_type=student_type,
                school_year=school_year,
                reason="http_error",
                inner_data={
                    "error": "http_error",
                    "status_code": response.status_code,
                    "body": response.text[:2000],
                },
            )

        # --------------------------------------------------------------
        # 3) Unwrap OK payload from A2A
        # --------------------------------------------------------------
        result = response.json()
        logger.info("Registration raw result from A2A: %s", result)

        registration_run = result.get("registration_run", {}) or {}

        inner_payload = None
        if isinstance(registration_run.get("answer"), dict):
            inner_payload = registration_run["answer"]
        else:
            op = registration_run.get("output_preview")
            if isinstance(op, dict):
                inner_payload = op
            elif isinstance(op, str):
                try:
                    inner_payload = ast.literal_eval(op)
                except Exception as e:
                    logger.warning(
                        "Failed to parse output_preview as dict: %s op=%r",
                        e,
                        op[:200],
                    )
                    inner_payload = None

        # --------------------------------------------------------------
        # 4) Extract final answer / metadata
        # --------------------------------------------------------------
        registration_answer_text = "No details available."
        registration_intent = "register_new_student"
        registration_agent_id = agent_id
        registration_agent_name = agent_name
        inner_data: dict = {}

        if isinstance(inner_payload, dict):
            inner_data = inner_payload

            registration_answer_text = (
                inner_payload.get("answer")
                or inner_payload.get("message")
                or "No details available."
            )

            registration_intent = inner_payload.get(
                "intent",
                registration_run.get("intent", "register_new_student"),
            )

            registration_agent_id = (
                inner_payload.get("agent_id")
                or registration_run.get("agent_id")
                or agent_id
            )

            registration_agent_name = (
                inner_payload.get("agent_name")
                or registration_run.get("agent_name")
                or agent_name
            )

            registration_session_id = (
                inner_payload.get("agent_session_id")
                or registration_run.get("agent_session_id")
                or registration_session_id
            )
        else:
            op = registration_run.get("output_preview") or "No details available."
            registration_answer_text = str(op)

            registration_intent = registration_run.get(
                "intent",
                "register_new_student",
            )

            registration_agent_id = registration_run.get("agent_id") or agent_id
            registration_agent_name = registration_run.get("agent_name") or agent_name
            registration_session_id = (
                registration_run.get("agent_session_id") or registration_session_id
            )

        # Normalize inner dict-style results if needed
        if isinstance(registration_answer_text, str):
            stripped = registration_answer_text.strip()
            if stripped.startswith("{") and (
                "'answer'" in stripped or '"answer"' in stripped
            ):
                try:
                    maybe_dict = ast.literal_eval(stripped)
                    if isinstance(maybe_dict, dict) and "answer" in maybe_dict:
                        registration_answer_text = maybe_dict["answer"]
                except Exception as e:
                    logger.warning(
                        "Failed to normalize registration_answer_text as dict: %s text=%r",
                        e,
                        stripped[:200],
                    )

        # --------------------------------------------------------------
        # 4b) Prefix answer with session-mode info (new vs continue)
        # --------------------------------------------------------------
        prefix_lines: list[str] = []

        if session_mode == "new":
            if existing_registration_session_id:
                prefix_lines.append(
                    "Okay, I’ve started a new registration for a different student."
                )
            else:
                prefix_lines.append("Okay, I’ve started a new registration.")
            prefix_lines.append(f"Registration session ID: {registration_session_id}")
        elif session_mode == "continue":
            prefix_lines.append("Okay, continuing your existing registration.")
            prefix_lines.append(f"Registration session ID: {registration_session_id}")

        if prefix_lines:
            registration_answer_text = (
                "\n\n".join(prefix_lines) + "\n\n" + str(registration_answer_text)
            )

        # Debug chunk for Sources UI
        debug_neighbors = [
            {
                "score": 1.0,
                "filename": "registration_run",
                "chunk_index": None,
                "text_preview": str(registration_answer_text)[:800],
                "image_paths": None,
                "page_index": None,
                "page_chunk_index": None,
            }
        ]

        # Persist final values
        _set_registration_state(
            registration_session_id,
            student_type=student_type,
            school_year=school_year,
        )

        # --------------------------------------------------------------
        # 5) FINAL RETURN (with debug info)
        # --------------------------------------------------------------
        debug_payload = self._build_debug_payload(
            phase="final",
            ctx=ctx,
            session_mode=session_mode,
            existing_registration_session_id=existing_registration_session_id,
            registration_session_id=registration_session_id,
            student_type=student_type,
            school_year=school_year,
            registration_run=registration_run,
            inner_data=inner_data,
        )

        return AgentResult(
            answer_text=registration_answer_text,
            intent=registration_intent or "register_new_student",
            index="registration",
            agent_id=registration_agent_id,
            agent_name=registration_agent_name,
            extra_chunks=debug_neighbors,
            status=registration_run.get("status", "ok"),
            agent_session_id=registration_session_id,
            data={
                "registration_run": registration_run,
                "inner_data": inner_data,
                "student_type": student_type,
                "school_year": school_year,
                "agent_debug_information": debug_payload,
            },
        )
