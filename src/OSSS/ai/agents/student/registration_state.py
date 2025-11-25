from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Protocol

# Dedicated logger for state-management operations.
# Every read/write of registration state should flow through here,
# which makes it easy to:
#   - turn on DEBUG and see exactly how state changes over time
#   - filter logs by this logger name in centralized logging
logger = logging.getLogger("OSSS.ai.agents.registration.state")


# ======================================================================
# RegistrationSessionState
# ======================================================================
@dataclass
class RegistrationSessionState:
    """
    Represents all tracked state for a single *registration session*.

    Conceptually
    ------------
    - One `RegistrationSessionState` instance corresponds to one logical
      registration workflow across multiple turns/messages.
    - It is independent of the raw chat history; this is more like
      a “wizard state” that the agent uses to remember what information
      has been collected so far.

    Why keep it separate from chat?
    --------------------------------
    - Chat history can be long, noisy, and unstructured.
    - The registration flow has a relatively small, well-defined set of
      fields we care about (student_type, school_year, etc.).
    - By modeling those explicitly, the dialog policy can reason about
      “what’s missing” and “what we already know” in a clean way.

    Attributes
    ----------
    session_id : str
        A unique identifier for the registration interaction.
        - Typically this is a UUID string.
        - It is the “primary key” used by the state store.
        - The same ID may be used in A2A payloads so the external
          registration service can correlate calls.

    student_type : Optional[str]
        Indicates whether the user is registering a:
            - "new"      student (brand new enrollee)
            - "existing" student (previously attended DCG)
            - or None    (not yet provided / unknown)
        This is a plain string (instead of a Literal) to keep the
        stored payload flexible; the dialog policy enforces meaning.

    school_year : Optional[str]
        A normalized school-year string such as "2025-26",
        or None if the user has not specified it yet.

        Normalization examples:
            - User says "2025/26"  -> "2025-26"
            - User says "2025–26"  -> "2025-26"
        The actual normalization step is performed in the dialog layer,
        not here — this dataclass simply stores the chosen representation.
    """

    # Unique identifier for this registration session
    session_id: str

    # What kind of student: "new" / "existing" / None
    student_type: Optional[str] = None

    # School year like "2025-26", or None if not yet known
    school_year: Optional[str] = None


# ======================================================================
# RegistrationStateStore (interface)
# ======================================================================
class RegistrationStateStore(Protocol):
    """
    Abstract storage backend for persisting registration session state.

    Why this abstraction exists
    ---------------------------
    - The agent logic should not know or care *where* the state is stored.
      It only needs:
          * `get(session_id)`  to retrieve a RegistrationSessionState
          * `upsert(state)`    to persist changes
    - Concrete implementations can be swapped in without touching the
      agent or dialog logic, enabling:
          * in-memory stores (for tests)
          * Redis or Memcached caches
          * relational databases (PostgreSQL, MySQL)
          * document stores (MongoDB, DynamoDB)
          * actor-based local/remote memory, etc.

    This keeps the codebase modular and easy to evolve as scaling and
    reliability requirements change.

    Methods
    -------
    async def get(session_id: str) -> Optional[RegistrationSessionState]:
        Retrieve the session state with the given `session_id`, or return
        None if this session is unknown.

    async def upsert(state: RegistrationSessionState) -> None:
        Insert the new state or overwrite the existing one for the given
        `state.session_id`.
    """

    async def get(self, session_id: str) -> Optional[RegistrationSessionState]:
        """
        Fetch the RegistrationSessionState for a given session_id.

        Implementations may:
            - read from a dict (in-memory)
            - execute a SELECT query
            - call an external key/value service
        """
        ...

    async def upsert(self, state: RegistrationSessionState) -> None:
        """
        Insert or update (upsert) the provided state object.

        Implementations may:
            - simply assign into a dict
            - perform INSERT ... ON CONFLICT
            - use SET on a Redis hash, etc.
        """
        ...


# ======================================================================
# InMemoryRegistrationStateStore
# ======================================================================
class InMemoryRegistrationStateStore:
    """
    A simple, in-process dictionary-backed store for registration state.

    ⚠ IMPORTANT: This is *not* suitable for production usage:
        - Does not persist to disk.
        - Lost on restart (e.g., process restart wipes all sessions).
        - Cannot be shared across worker processes or containers.
        - Cannot be scaled horizontally across multiple instances.

    It *is* ideal for:
        - Local development
        - Unit / integration testing
        - Ephemeral environments (Playgrounds, dev shells)
        - Quick demos where durability and sharing are not required.

    Design intent
    -------------
    - Keep the implementation deliberately straightforward so that
      behavior is completely obvious while debugging.
    - Emit detailed DEBUG logs on every read/write, which helps you
      reconstruct the full lifecycle of a registration session
      from the logs alone.
    """

    def __init__(self) -> None:
        # Internal in-memory mapping:
        #   session_id (str) -> RegistrationSessionState
        # This is the single source of truth for session data in this implementation.
        self._store: Dict[str, RegistrationSessionState] = {}

        logger.debug(
            "[InMemoryRegistrationStateStore.__init__] Initialized empty "
            "in-memory registration state store."
        )

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------
    async def get(self, session_id: str) -> Optional[RegistrationSessionState]:
        """
        Retrieve the state object for a given session_id.

        Parameters
        ----------
        session_id : str
            The unique ID assigned to the registration session.
            This should match the `session_id` used by the agent and
            included in A2A payloads.

        Returns
        -------
        RegistrationSessionState or None
            Returns the stored state if present; otherwise returns None.

        Logging
        -------
        - At DEBUG level, logs:
            * The requested session_id
            * Whether a state object was found or not
        """
        state = self._store.get(session_id)

        logger.debug(
            "[InMemoryRegistrationStateStore.get] Looking up session_id=%s | Found=%s",
            session_id,
            "YES" if state is not None else "NO",
        )

        return state

    # ------------------------------------------------------------------
    # upsert
    # ------------------------------------------------------------------
    async def upsert(self, state: RegistrationSessionState) -> None:
        """
        Insert or update the state for a given registration session.

        Parameters
        ----------
        state : RegistrationSessionState
            The updated state to persist. The key used for storage is
            `state.session_id`.

        Notes
        -----
        - This method will overwrite any existing state under the
          same session_id. (Hence the term "upsert".)
        - The full before/after state is logged at DEBUG level to
          help trace changes across turns. This can be invaluable
          when debugging subtle dialog/branching bugs.

        Concurrency
        -----------
        - This implementation is *not* thread-safe. In many async
          Python deployments this is fine (single-threaded event loop),
          but for multi-threaded or multi-process environments you
          should use a real shared store instead.
        """
        before = self._store.get(state.session_id)

        logger.debug(
            "[InMemoryRegistrationStateStore.upsert] Writing state for session_id=%s\n"
            "  BEFORE: %s\n"
            "  AFTER:  %s",
            state.session_id,
            before,
            state,
        )

        # Overwrite (or create) the entry. Since RegistrationSessionState
        # is a dataclass, it's easy to compare before/after in logs.
        self._store[state.session_id] = state
