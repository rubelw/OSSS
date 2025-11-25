# src/OSSS/ai/agents/student/registration_state_store.py
from __future__ import annotations

from typing import Dict, Optional
import asyncio
import logging

from .registration_state import RegistrationSessionState

logger = logging.getLogger("OSSS.ai.agents.registration_state_store")


class RegistrationStateStore:
    """
    Very simple async in-memory store for RegistrationSessionState.

    This is fine for local dev or single-process deployment.
    For multi-worker production, replace internals with Redis/DB and
    keep the same async interface.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._states: Dict[str, RegistrationSessionState] = {}

    async def get(self, session_id: str) -> Optional[RegistrationSessionState]:
        """
        Return the current state for this session_id, or None if not found.
        """
        async with self._lock:
            state = self._states.get(session_id)
            if state:
                logger.debug(
                    "Loaded RegistrationSessionState for session_id=%s: %r",
                    session_id,
                    state,
                )
            else:
                logger.debug(
                    "No existing RegistrationSessionState for session_id=%s",
                    session_id,
                )
            return state

    async def save(self, state: RegistrationSessionState) -> None:
        """
        Upsert the state for this session_id.
        """
        async with self._lock:
            state.touch()
            self._states[state.session_id] = state
            logger.debug(
                "Saved RegistrationSessionState for session_id=%s: %r",
                state.session_id,
                state,
            )

    async def delete(self, session_id: str) -> None:
        """
        Optional: clear state when a registration flow is fully complete.
        """
        async with self._lock:
            if session_id in self._states:
                del self._states[session_id]
                logger.debug(
                    "Deleted RegistrationSessionState for session_id=%s",
                    session_id,
                )
