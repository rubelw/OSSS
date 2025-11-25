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
    """
    Normalized view of the registration service response.

    We keep it flexible because the real service schema may evolve.
    """

    confirmation_id: Optional[str] = None
    status: Optional[str] = None
    raw: Dict[str, Any]


class RegistrationServiceClient:
    """
    Thin async HTTP client for the student registration backend.

    You can extend this with more methods as your service grows
    (validate_registration, get_registration, etc.).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (base_url or getattr(settings, "REGISTRATION_SERVICE_URL", "http://a2a:8086")).rstrip("/")
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

        Returns a normalized RegistrationServiceResponse.
        """
        payload: Dict[str, Any] = {
            "session_id": state.session_id,
            "session_mode": state.session_mode,
            "student_type": state.student_type,
            "school_year": state.school_year,
            "student_first_name": state.student_first_name,
            "student_last_name": state.student_last_name,
            # add more fields as you extend RegistrationSessionState
        }

        logger.info(
            "Calling registration service at %s with payload=%r",
            self.registration_url,
            payload,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.registration_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Try to pull out a confirmation identifier from common keys
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
