"""
API Factory for production and testing environments.

This module provides a centralized factory for constructing and managing
the Orchestration API used by OSSS / OSSS.

Key responsibilities:
- Environment-driven API selection (real vs mock)
- Singleton-style instance caching
- Safe initialization and shutdown lifecycle management
- Test-friendly overrides and temporary mode switching
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import os  # Environment variable access
from typing import Optional, Any, Dict

# ---------------------------------------------------------------------------
# OSSS / OSSS imports
# ---------------------------------------------------------------------------

# Base interface / protocol for orchestration APIs
from OSSS.ai.api.external import OrchestrationAPI

# Production implementation backed by LangGraph
from OSSS.ai.api.orchestration_api import LangGraphOrchestrationAPI

# Centralized structured logger
from OSSS.ai.observability import get_logger

# Module-level logger
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Global singleton cache
# ---------------------------------------------------------------------------
# The orchestration API is treated as a process-wide singleton.
# This avoids:
# - Repeated expensive initialization
# - Multiple competing graph runtimes
# - Inconsistent execution state
#
# NOTE:
# This is intentionally mutable global state, with explicit reset helpers
# for testing and controlled lifecycle management.
_cached_orchestration_api: Optional[OrchestrationAPI] = None


def get_orchestration_api(force_mode: Optional[str] = None) -> OrchestrationAPI:
    """
    Retrieve an orchestration API instance with singleton caching.

    This function:
    - Returns a cached API instance if one already exists
    - Selects the API implementation based on environment or override
    - Lazily constructs the API on first access

    Args:
        force_mode : Optional[str]
            Optional override for API mode.
            Valid values: "real", "mock"

    Returns:
        OrchestrationAPI
            A concrete API implementation (real or mock)
    """
    global _cached_orchestration_api

    # -----------------------------------------------------------------------
    # Fast path: return cached instance if it exists
    # -----------------------------------------------------------------------
    if _cached_orchestration_api is not None:
        logger.debug(
            f"[factory] Returning cached API: "
            f"{_cached_orchestration_api.__class__.__name__}"
        )
        return _cached_orchestration_api

    # -----------------------------------------------------------------------
    # Determine API mode
    # -----------------------------------------------------------------------
    # Priority:
    # 1. Explicit force_mode argument
    # 2. Environment variable COGNIVAULT_API_MODE
    # 3. Default to "real"
    api_mode = force_mode or os.getenv("COGNIVAULT_API_MODE", "real")

    # -----------------------------------------------------------------------
    # Instantiate appropriate API implementation
    # -----------------------------------------------------------------------
    if api_mode and api_mode.lower() == "mock":
        logger.info("[factory] Using MockOrchestrationAPI")

        # Deferred import avoids:
        # - Circular dependencies
        # - Test-only dependencies leaking into production
        from tests.fakes.mock_orchestration import MockOrchestrationAPI

        _cached_orchestration_api = MockOrchestrationAPI()
    else:
        logger.info("[factory] Using LangGraphOrchestrationAPI")
        _cached_orchestration_api = LangGraphOrchestrationAPI()

    # Log creation for observability
    logger.info(
        f"[factory] Created new API instance: "
        f"{_cached_orchestration_api.__class__.__name__}"
    )

    return _cached_orchestration_api


def reset_api_cache() -> None:
    """
    Reset the cached API instance.

    This is primarily intended for:
    - Test isolation
    - Mode switching (real ↔ mock)
    - Controlled teardown and recreation

    NOTE:
    This does NOT call shutdown(). That responsibility is handled separately.
    """
    global _cached_orchestration_api

    if _cached_orchestration_api:
        logger.info(
            f"[factory] Resetting API cache "
            f"(was: {_cached_orchestration_api.__class__.__name__})"
        )
    else:
        logger.debug("[factory] Resetting API cache (was: None)")

    _cached_orchestration_api = None


async def initialize_api(force_mode: Optional[str] = None) -> OrchestrationAPI:
    """
    Retrieve and initialize the orchestration API instance.

    This function ensures:
    - The API is created (if needed)
    - Initialization occurs only once
    - Repeated calls are idempotent

    Args:
        force_mode : Optional[str]
            Optional override for API mode.

    Returns:
        OrchestrationAPI
            Fully initialized API instance
    """
    api = get_orchestration_api(force_mode)

    # -----------------------------------------------------------------------
    # Guard against double initialization
    # -----------------------------------------------------------------------
    # Many APIs perform expensive setup during initialization
    # (network connections, model loading, graph compilation, etc.)
    if hasattr(api, "_initialized") and api._initialized:
        logger.debug(
            f"[factory] API already initialized: {api.__class__.__name__}"
        )
        return api

    # -----------------------------------------------------------------------
    # Perform initialization
    # -----------------------------------------------------------------------
    logger.info(f"[factory] Initializing API: {api.__class__.__name__}")
    await api.initialize()
    logger.info(
        f"[factory] API initialization complete: {api.__class__.__name__}"
    )

    return api


async def shutdown_api() -> None:
    """
    Shut down the cached orchestration API instance, if one exists.

    This function:
    - Calls the API's shutdown hook
    - Handles shutdown errors gracefully
    - Resets the cache afterward to avoid reuse
    """
    global _cached_orchestration_api

    if _cached_orchestration_api:
        logger.info(
            f"[factory] Shutting down API: "
            f"{_cached_orchestration_api.__class__.__name__}"
        )
        try:
            await _cached_orchestration_api.shutdown()
        except Exception as e:
            # Shutdown failures should never crash the process
            logger.error(f"[factory] Error during API shutdown: {e}")
        finally:
            reset_api_cache()
    else:
        logger.debug("[factory] No cached API to shutdown")


def get_api_mode() -> str:
    """
    Retrieve the current API mode from environment configuration.

    Returns:
        str
            Current API mode ("real" or "mock")
    """
    return os.getenv("COGNIVAULT_API_MODE", "real").lower()


def set_api_mode(mode: str) -> None:
    """
    Set the API mode via environment variable.

    IMPORTANT:
    This does NOT affect already cached API instances.
    You must call reset_api_cache() to force recreation.

    Args:
        mode : str
            API mode to set ("real" or "mock")

    Raises:
        ValueError
            If an invalid mode is provided
    """
    if mode.lower() not in ["real", "mock"]:
        raise ValueError(
            f"Invalid API mode: {mode}. Must be 'real' or 'mock'"
        )

    os.environ["COGNIVAULT_API_MODE"] = mode.lower()
    logger.info(f"[factory] Set API mode to: {mode.lower()}")


def is_mock_mode() -> bool:
    """
    Determine whether the system is currently configured for mock mode.

    Returns:
        bool
            True if mock mode is active, False otherwise
    """
    return get_api_mode() == "mock"


def get_cached_api_info() -> Optional[Dict[str, Any]]:
    """
    Retrieve metadata about the currently cached API instance.

    This is useful for:
    - Debug endpoints
    - Health checks
    - Diagnostics and observability

    Returns:
        Optional[Dict[str, Any]]
            Dictionary of API metadata, or None if no API is cached
    """
    global _cached_orchestration_api

    if _cached_orchestration_api is None:
        return None

    return {
        "class_name": _cached_orchestration_api.__class__.__name__,
        "api_name": _cached_orchestration_api.api_name,
        "api_version": _cached_orchestration_api.api_version,
        "initialized": getattr(
            _cached_orchestration_api, "_initialized", False
        ),
        "mode": get_api_mode(),
    }


# ---------------------------------------------------------------------------
# Context manager for temporary API mode switching
# ---------------------------------------------------------------------------

class TemporaryAPIMode:
    """
    Context manager for temporarily switching API mode.

    This is especially useful in tests where:
    - A mock API is required for a specific scope
    - Global environment state must be restored afterward

    Example:
        with TemporaryAPIMode("mock"):
            api = get_orchestration_api()
            # api is MockOrchestrationAPI inside this block
    """

    def __init__(self, mode: str) -> None:
        # Normalize and validate requested mode
        self.new_mode = mode.lower()
        self.original_mode = get_api_mode()

        if self.new_mode not in ["real", "mock"]:
            raise ValueError(
                f"Invalid API mode: {mode}. Must be 'real' or 'mock'"
            )

    def __enter__(self) -> "TemporaryAPIMode":
        # Only change state if mode is actually different
        if self.new_mode != self.original_mode:
            set_api_mode(self.new_mode)
            reset_api_cache()  # Force recreation with new mode
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        # Restore original environment and cache state
        if self.new_mode != self.original_mode:
            set_api_mode(self.original_mode)
            reset_api_cache()
