from __future__ import annotations

from typing import Dict

from .students_state import StudentQueryState


class StudentQueryStateStore:
    """
    Abstract-ish interface so you can later plug in Redis/Postgres/etc.
    """

    async def get(self, session_id: str) -> StudentQueryState:  # pragma: no cover - interface
        raise NotImplementedError

    async def save(self, state: StudentQueryState) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryStudentQueryStateStore(StudentQueryStateStore):
    """
    Simple in-process store keyed by session_id.

    This mirrors the pattern from your registration state store, but is
    intentionally minimal.
    """

    def __init__(self) -> None:
        self._states: Dict[str, StudentQueryState] = {}

    async def get(self, session_id: str) -> StudentQueryState:
        state = self._states.get(session_id)
        if state is None:
            state = StudentQueryState(session_id=session_id)
            self._states[session_id] = state
        return state

    async def save(self, state: StudentQueryState) -> None:
        self._states[state.session_id] = state
