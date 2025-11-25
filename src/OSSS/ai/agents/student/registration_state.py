from __future__ import annotations

import asyncio
from typing import Optional, Dict
from pydantic import BaseModel


class RegistrationSessionState(BaseModel):
    """
    Represents saved progress of a registration workflow.
    """
    session_id: str
    student_type: Optional[str] = None   # "new" | "existing"
    school_year: Optional[str] = None    # "2025-26", etc.


class RegistrationStateStore:
    """
    In-memory async-safe storage for RegistrationSessionState.
    In production you can replace this with Redis, Postgres, etc.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._store: Dict[str, RegistrationSessionState] = {}

    async def get(self, session_id: str) -> Optional[RegistrationSessionState]:
        async with self._lock:
            return self._store.get(session_id)

    async def upsert(self, state: RegistrationSessionState) -> None:
        async with self._lock:
            self._store[state.session_id] = state

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._store:
                del self._store[session_id]
