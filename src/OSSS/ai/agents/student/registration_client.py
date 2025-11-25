# src/OSSS/ai/agents/student/registration_client.py
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

import httpx
from pydantic import BaseModel

from .registration_state import RegistrationSessionState

logger = logging.getLogger("OSSS.ai.agents.registration_client")

# Try to use your real settings if available
try:
    from OSSS.config import settings as _settings  # type: ignore

    settings = _settings
except Exception:  # pragma: no cover - test / fallback
    class _Settings:
        REGISTRATION_SERVICE_URL: str = "http://a2a:8086"
        REGISTRATION_ENDPOINT_PATH: str = "/admin/registration"

    settings = _Settings()  # type: ignore


class RegistrationServiceResponse(BaseModel):
    confirmation_id: Optional[str] = None
    status: Optional[str] = None
    raw: Dict[str, Any]


class RegistrationServiceClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (
            base_url
            or getattr(settings, "REGISTRATION_SERVICE_URL", "http://a2a:8086")
        ).rstrip("/")
        self.endpoint_path = endpoint_path or getattr(
            settings,
            "REGISTRATION_ENDPOINT_PATH",
            "/admin/registration",
        )
        self.timeout = timeout

    @property
    def registration_url(self) -> str:
        return f"{self.base_url}{self.endpoint_path}"

    async def submit_registration(
        self,
        state: RegistrationSessionState,
    ) -> RegistrationServiceResponse:
        """
        Submit the registration represented by `state` to the backend service.

        For `session_mode == "continue"`, send only the minimal identifiers but
        still include all fields required by the A2A FastAPI model:
        - query
        - registration_agent_id
        - registration_skill
        """

        # Base payload for a NEW registration
        base_payload: Dict[str, Any] = {
            "session_id": state.session_id,
            "session_mode": state.session_mode,
            # These three are REQUIRED by the A2A endpoint (per 422 error):
            "query": "start registration",                 # or any label you like
            "registration_agent_id": "register_new_student",
            "registration_skill": "student_registration",
            # Your existing fields:
            "student_type": state.student_type,
            "school_year": state.school_year,
            "student_first_name": getattr(state, "student_first_name", None),
            "student_last_name": getattr(state, "student_last_name", None),
            # add more fields as you extend RegistrationSessionState
        }

        if state.session_mode == "continue":
            # For CONTINUE, keep it minimal but still satisfy A2A's required fields
            payload: Dict[str, Any] = {
                "session_id": state.session_id,
                "session_mode": state.session_mode,
                "query": "continue registration",
                "registration_agent_id": "register_new_student",
                "registration_skill": "student_registration",
            }
        else:
            payload = base_payload

        # Strip out any None values so we don't send nulls unnecessarily
        payload = {k: v for k, v in payload.items() if v is not None}

        logger.info(
            "Calling registration service at %s with payload=%r",
            self.registration_url,
            payload,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.registration_url, json=payload)

            if resp.status_code >= 400:
                logger.error(
                    "[RegistrationServiceClient] A2A returned %s: %s",
                    resp.status_code,
                    resp.text[:2000],
                )
                resp.raise_for_status()

            data = resp.json()

        confirmation_id = (
            data.get("confirmation_id")
            or data.get("id")
            or data.get("registration_id")
        )
        status = data.get("status") or "ok"

        logger.info(
            "Registration service response: status=%s confirmation_id=%r raw_len=%s",
            status,
            confirmation_id,
            len(str(data)),
        )

        return RegistrationServiceResponse(
            confirmation_id=str(confirmation_id) if confirmation_id is not None else None,
            status=status,
            raw=data,
        )