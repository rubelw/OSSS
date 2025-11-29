from __future__ import annotations

import logging
from typing import Any, List, Optional

import httpx

logger = logging.getLogger("OSSS.ai.agents.query_data.client")

# Safe settings import (same pattern you used elsewhere)
try:
    from OSSS.config import settings as _settings  # type: ignore

    settings = _settings
except Exception:
    class _Settings:
        STUDENT_API_BASE: str = "http://localhost:8081"

    settings = _Settings()  # type: ignore


class StudentsServiceClient:
    """
    Thin async client around the external Students API.

    Default endpoint:
      GET {base_url}/api/students?skip=<int>&limit=<int>
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (
            base_url or getattr(settings, "STUDENT_API_BASE", "http://localhost:8081")
        ).rstrip("/")
        self.timeout = timeout

    async def list_students(self, skip: int = 0, limit: int = 100) -> List[dict[str, Any]]:
        url = f"{self.base_url}/api/students"
        params = {"skip": skip, "limit": limit}

        logger.info(
            "[query_data.client] GET %s params=%s",
            url,
            params,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=params)
            logger.info(
                "[query_data.client] status=%s bytes=%s",
                resp.status_code,
                len(resp.content),
            )
            resp.raise_for_status()
            data = resp.json()

        # Handle either a plain list or an {items: [...]} envelope
        if isinstance(data, dict) and "items" in data:
            students = data["items"]
        elif isinstance(data, list):
            students = data
        else:
            logger.warning(
                "[query_data.client] unexpected response shape: %r",
                data,
            )
            students = []

        if not isinstance(students, list):
            logger.warning(
                "[query_data.client] students is not a list: %r",
                students,
            )
            return []

        return students
