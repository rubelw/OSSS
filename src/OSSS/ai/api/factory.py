"""
API Factory for production and testing environments.

This module provides a centralized factory for constructing and managing
the Orchestration API used by OSSS / OSSS.

Key responsibilities:
- Environment-driven API selection (real vs mock)
- Singleton-style instance caching (per-process)
- Safe initialization and shutdown lifecycle management
- Test-friendly overrides and temporary mode switching
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import asyncio
import os
from typing import Optional, Any, Dict

# ---------------------------------------------------------------------------
# OSSS imports
# ---------------------------------------------------------------------------

from OSSS.ai.api.external import OrchestrationAPI
from OSSS.ai.api.orchestration_api import LangGraphOrchestrationAPI
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Global singleton cache (per-process)
# -----------------------------------------------------------------------------
_api_instance: Optional[OrchestrationAPI] = None
_api_lock = asyncio.Lock()


async def get_orchestration_api(force_mode: Optional[str] = None) -> OrchestrationAPI:
    """
    Async factory that returns a fully-initialized orchestration API instance.

    Safe to call from FastAPI routes and other async contexts.

    Behavior:
    - Returns cached instance if present
    - Creates instance based on mode (real/mock) if absent
    - Calls await api.initialize() exactly once per process (idempotent)
    - Uses an async lock to prevent concurrent double initialization
    """
    global _api_instance

    if _api_instance is not None:
        logger.info(f"[factory] Using cached API instance: {type(_api_instance).__name__}")
        return _api_instance

    async with _api_lock:
        # Re-check after acquiring lock (another coroutine may have initialized)
        if _api_instance is not None:
            logger.info(f"[factory] Using cached API instance: {type(_api_instance).__name__}")
            return _api_instance

        mode = (force_mode or os.getenv("OSSS_API_MODE", "real")).lower()

        if mode == "mock":
            logger.info("[factory] Using MockOrchestrationAPI")
            # Deferred import avoids circular deps + test deps in prod
            from tests.fakes.mock_orchestration import MockOrchestrationAPI

            api: OrchestrationAPI = MockOrchestrationAPI()
        else:
            logger.info("[factory] Using LangGraphOrchestrationAPI")
            api = LangGraphOrchestrationAPI()

        # Always initialize (initialize() should be idempotent)
        logger.info(f"[factory] Initializing API: {type(api).__name__}")
        await api.initialize()
        logger.info(f"[factory] API initialization complete: {type(api).__name__}")

        _api_instance = api
        logger.info(f"[factory] Created + cached API instance: {type(_api_instance).__name__}")
        return _api_instance


def reset_api_cache() -> None:
    """
    Reset the cached API instance.

    NOTE: This does NOT call shutdown(). Use shutdown_api() for that.
    """
    global _api_instance

    if _api_instance:
        logger.info(f"[factory] Resetting API cache (was: {type(_api_instance).__name__})")
    else:
        logger.debug("[factory] Resetting API cache (was: None)")

    _api_instance = None


async def shutdown_api() -> None:
    """
    Shut down the cached orchestration API instance, if one exists.

    This function:
    - Calls the API's shutdown hook
    - Handles shutdown errors gracefully
    - Resets the cache afterward to avoid reuse
    """
    global _api_instance

    if _api_instance is None:
        logger.debug("[factory] No cached API to shutdown")
        return

    logger.info(f"[factory] Shutting down API: {type(_api_instance).__name__}")
    try:
        await _api_instance.shutdown()
    except Exception as e:
        logger.error(f"[factory] Error during API shutdown: {e}")
    finally:
        reset_api_cache()


def get_api_mode() -> str:
    """Return current API mode ('real' or 'mock') from environment."""
    return os.getenv("OSSS_API_MODE", "real").lower()


def set_api_mode(mode: str) -> None:
    """
    Set the API mode via environment variable.

    IMPORTANT:
    This does NOT affect an already cached API instance.
    Call reset_api_cache() to force recreation.
    """
    m = mode.lower()
    if m not in ("real", "mock"):
        raise ValueError(f"Invalid API mode: {mode}. Must be 'real' or 'mock'")

    os.environ["OSSS_API_MODE"] = m
    logger.info(f"[factory] Set API mode to: {m}")


def is_mock_mode() -> bool:
    """True if configured for mock mode."""
    return get_api_mode() == "mock"


def get_cached_api_info() -> Optional[Dict[str, Any]]:
    """
    Return metadata about the cached API instance, or None if not cached.
    """
    global _api_instance

    if _api_instance is None:
        return None

    return {
        "class_name": type(_api_instance).__name__,
        "api_name": _api_instance.api_name,
        "api_version": _api_instance.api_version,
        "initialized": getattr(_api_instance, "_initialized", False),
        "mode": get_api_mode(),
    }


class TemporaryAPIMode:
    """
    Context manager for temporarily switching API mode.

    Example:
        with TemporaryAPIMode("mock"):
            api = await get_orchestration_api()
    """

    def __init__(self, mode: str) -> None:
        self.new_mode = mode.lower()
        self.original_mode = get_api_mode()

        if self.new_mode not in ("real", "mock"):
            raise ValueError(f"Invalid API mode: {mode}. Must be 'real' or 'mock'")

    def __enter__(self) -> "TemporaryAPIMode":
        if self.new_mode != self.original_mode:
            set_api_mode(self.new_mode)
            reset_api_cache()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.new_mode != self.original_mode:
            set_api_mode(self.original_mode)
            reset_api_cache()
