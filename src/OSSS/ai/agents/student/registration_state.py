from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class RegistrationSessionState(BaseModel):
    """
    Persistent dialog state for a registration session.
    """

    # Unique ID for this registration dialog session
    session_id: str

    # Dialog-level mode: "new" or "continue"
    session_mode: Optional[Literal["new", "continue"]] = None

    # NEW vs EXISTING student (slot 1)
    student_type: Optional[str] = None

    # School year (slot 2)
    school_year: Optional[str] = None

    # Parent / guardian information (slot 3)
    parent_first_name: Optional[str] = None
    parent_last_name: Optional[str] = None
    parent_email: Optional[str] = None
    parent_email_verify: Optional[str] = None

    student_documents_confirmed: Optional[bool] = None

    # Student fields if needed (slot 4)
    student_first_name: Optional[str] = None
    student_last_name: Optional[str] = None

    # Whether any registered student has previously attended DC-G
    student_has_attended_before: Optional[bool] = None

    # Outcome of last A2A registration service call
    registration_run: Optional[str] = None

    # Freeform scratch space used by dialog engine
    inner_data: Dict[str, Any] = Field(default_factory=dict)
    proof_of_residency_upload: Optional[str] = None



class RegistrationStateStore:
    """
    In-memory async-safe storage for :class:`RegistrationSessionState`.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._store: Dict[str, RegistrationSessionState] = {}

    async def get(self, session_id: str) -> Optional[RegistrationSessionState]:
        async with self._lock:
            return self._store.get(session_id)

    async def save(self, state: RegistrationSessionState) -> None:
        async with self._lock:
            self._store[state.session_id] = state

    # backwards compatible
    async def upsert(self, state: RegistrationSessionState) -> None:
        await self.save(state)

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._store:
                del self._store[session_id]


# 🔧 Fix for Pydantic 2 + postponed annotations
RegistrationSessionState.model_rebuild()
