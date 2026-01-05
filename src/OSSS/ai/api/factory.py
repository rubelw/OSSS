from __future__ import annotations

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

import asyncio
import inspect
import os
from typing import Any, Dict, Optional

from OSSS.ai.api.external import OrchestrationAPI
from OSSS.ai.api.orchestration_api import LangGraphOrchestrationAPI
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

_api_instance: Optional[OrchestrationAPI] = None
_api_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Dependency wiring helpers
# ---------------------------------------------------------------------------

def _import_first(*candidates: str):
    """
    Try import paths in order. Each candidate is "module:attr" or "module".
    Returns imported attr/module. Raises ImportError if none succeed.
    """
    last_err: Optional[Exception] = None
    for cand in candidates:
        try:
            if ":" in cand:
                mod, attr = cand.split(":", 1)
                m = __import__(mod, fromlist=[attr])
                return getattr(m, attr)
            m = __import__(cand, fromlist=["*"])
            return m
        except Exception as e:
            last_err = e
    raise ImportError(f"Failed importing any of: {candidates!r}. Last error: {last_err}")


# ---------------------------------------------------------------------------
# Conversation state store (CRITICAL for turn-2 "yes/no" resume)
# ---------------------------------------------------------------------------

# Prefer a shared/persistent store to avoid "sometimes works" in multi-worker.
# We try DBConversationStateStore first, then optionally fall back to in-memory.
_conversation_store = None

# 1) DB store (recommended)
try:
    DBConversationStateStore = _import_first(
        "OSSS.ai.orchestration.state_store:DBConversationStateStore",
        "OSSS.ai.orchestration.state_store.db:DBConversationStateStore",
        "OSSS.ai.orchestration.state_store_impl:DBConversationStateStore",
    )

    # ✅ Updated wiring: DBConversationStateStore now uses async sessionmaker (or defaults)
    # Option A (explicit sessionmaker):
    get_sessionmaker = _import_first(
        "OSSS.db.session:get_sessionmaker",
        "OSSS.db.database:get_sessionmaker",
    )
    _conversation_store = DBConversationStateStore(sessionmaker=get_sessionmaker())

    # Option B (implicit default in store):
    # _conversation_store = DBConversationStateStore()

    logger.info(
        "[factory] Conversation store initialized (db)",
        extra={"store_type": type(_conversation_store).__name__},
    )
except Exception as e:
    _conversation_store = None
    logger.warning(
        "[factory] DB conversation store unavailable; turn-2 resume may be flaky in multi-worker deployments",
        extra={"error": str(e)},
    )

# 2) Optional fallback: in-process store (single-worker safe)
if _conversation_store is None:
    try:
        InMemoryConversationStateStore = getattr(
            LangGraphOrchestrationAPI, "InMemoryConversationStateStore", None
        )
        if InMemoryConversationStateStore is None:
            from OSSS.ai.api.orchestration_api import InMemoryConversationStateStore  # type: ignore

        _conversation_store = InMemoryConversationStateStore(ttl_seconds=3600)  # 1h TTL
        logger.info(
            "[factory] Conversation store initialized (in-memory fallback)",
            extra={"store_type": type(_conversation_store).__name__, "ttl_seconds": 3600},
        )
    except Exception as e:
        _conversation_store = None
        logger.warning(
            "[factory] Conversation store unavailable; turn-2 resume will NOT work without persistence",
            extra={"error": str(e)},
        )


def _build_langgraph_api() -> OrchestrationAPI:
    """
    Construct a LangGraphOrchestrationAPI with explicit dependency wiring.

    Best practice: the factory is the composition root.
    """
    # Prefer a class-level builder if present (lets orchestration_api own wiring)
    build_fn = getattr(LangGraphOrchestrationAPI, "build_default", None) or getattr(
        LangGraphOrchestrationAPI, "build", None
    )
    if callable(build_fn):
        logger.info("[factory] Building LangGraphOrchestrationAPI via class builder")
        api = build_fn()

        # Best-effort: if builder didn't wire a store, supply ours via attribute if supported.
        try:
            if getattr(api, "conversation_store", None) is None and _conversation_store is not None:
                setattr(api, "conversation_store", _conversation_store)
                logger.info(
                    "[factory] Injected conversation_store into built API",
                    extra={"store_type": type(_conversation_store).__name__},
                )
        except Exception:
            pass

        return api

    # Orchestrator
    try:
        LangGraphOrchestrator = _import_first(
            "OSSS.ai.orchestration.orchestrator:LangGraphOrchestrator",
        )
    except Exception as e:
        logger.exception("[factory] Failed importing LangGraphOrchestrator", extra={"error": str(e)})
        raise

    # Planner factory
    try:
        build_default_planner = _import_first(
            "OSSS.ai.orchestration.planning.defaults:build_default_planner",
        )
    except Exception as e:
        logger.exception("[factory] Failed importing build_default_planner", extra={"error": str(e)})
        raise

    # TurnNormalizer
    try:
        TurnNormalizer = _import_first(
            "OSSS.ai.orchestration.pipeline.turn_normalizer:TurnNormalizer",
            "OSSS.ai.orchestration.turn_normalizer:TurnNormalizer",
        )
    except Exception as e:
        logger.exception("[factory] Failed importing TurnNormalizer", extra={"error": str(e)})
        raise

    # ClassificationService (NOT ClassifierAgent)
    try:
        ClassificationService = _import_first(
            "OSSS.ai.services.classification_service:ClassificationService",
            "OSSS.ai.classification.service:ClassificationService",
            "OSSS.ai.services.classifier_service:ClassificationService",
        )
    except Exception as e:
        logger.exception(
            "[factory] Failed importing ClassificationService (required by LangGraphOrchestrationAPI)",
            extra={"error": str(e)},
        )
        raise

    # ✅ Conversation store (required for turn-2 resume of pending_action)
    conversation_store = _conversation_store
    logger.info(
        "[factory] Conversation store wired",
        extra={"store_type": type(conversation_store).__name__ if conversation_store else None},
    )

    # Instantiate
    try:
        orchestrator = LangGraphOrchestrator()
    except TypeError as e:
        sig = "<unknown>"
        try:
            sig = str(inspect.signature(LangGraphOrchestrator))
        except Exception:
            pass
        logger.exception(
            "[factory] LangGraphOrchestrator() requires constructor args; wire them here",
            extra={"error": str(e), "signature": sig},
        )
        raise

    planner = build_default_planner()

    try:
        classifier = ClassificationService()
    except TypeError as e:
        sig = "<unknown>"
        try:
            sig = str(inspect.signature(ClassificationService))
        except Exception:
            pass
        logger.exception(
            "[factory] ClassificationService() requires constructor args; wire them here",
            extra={"error": str(e), "signature": sig},
        )
        raise

    turn_normalizer = TurnNormalizer()

    # Diagnostics
    try:
        api_sig = str(inspect.signature(LangGraphOrchestrationAPI))
    except Exception:
        api_sig = "<unknown>"

    logger.info(
        "[factory] Constructing LangGraphOrchestrationAPI with explicit deps",
        extra={
            "LangGraphOrchestrationAPI_signature": api_sig,
            "deps": {
                "orchestrator": type(orchestrator).__name__,
                "planner": type(planner).__name__,
                "classifier": type(classifier).__name__,
                "turn_normalizer": type(turn_normalizer).__name__,
                "conversation_store": type(conversation_store).__name__ if conversation_store else None,
            },
        },
    )

    return LangGraphOrchestrationAPI(
        orchestrator=orchestrator,
        planner=planner,
        classifier=classifier,
        turn_normalizer=turn_normalizer,
        conversation_store=conversation_store,
    )


# ---------------------------------------------------------------------------
# Public factory functions
# ---------------------------------------------------------------------------

async def get_orchestration_api(force_mode: Optional[str] = None) -> OrchestrationAPI:
    global _api_instance

    if _api_instance is not None:
        logger.info("[factory] Using cached API instance: %s", type(_api_instance).__name__)
        return _api_instance

    async with _api_lock:
        if _api_instance is not None:
            logger.info("[factory] Using cached API instance: %s", type(_api_instance).__name__)
            return _api_instance

        mode = (force_mode or os.getenv("OSSS_API_MODE", "real")).lower()

        if mode == "mock":
            logger.info("[factory] Using MockOrchestrationAPI")
            from tests.fakes.mock_orchestration import MockOrchestrationAPI

            api: OrchestrationAPI = MockOrchestrationAPI()
        else:
            logger.info("[factory] Using LangGraphOrchestrationAPI")
            try:
                logger.info(
                    "[factory] LangGraphOrchestrationAPI diagnostics",
                    extra={
                        "class": repr(LangGraphOrchestrationAPI),
                        "file": inspect.getsourcefile(LangGraphOrchestrationAPI),
                        "abstract": sorted(getattr(LangGraphOrchestrationAPI, "__abstractmethods__", set())),
                        "signature": str(inspect.signature(LangGraphOrchestrationAPI)),
                    },
                )
            except Exception:
                logger.debug("[factory] LangGraphOrchestrationAPI diagnostics unavailable")

            api = _build_langgraph_api()

        logger.info("[factory] Initializing API: %s", type(api).__name__)
        await api.initialize()
        logger.info("[factory] API initialization complete: %s", type(api).__name__)

        _api_instance = api
        logger.info("[factory] Created + cached API instance: %s", type(_api_instance).__name__)
        return _api_instance


def reset_api_cache() -> None:
    global _api_instance
    if _api_instance:
        logger.info("[factory] Resetting API cache (was: %s)", type(_api_instance).__name__)
    else:
        logger.debug("[factory] Resetting API cache (was: None)")
    _api_instance = None


async def shutdown_api() -> None:
    global _api_instance
    if _api_instance is None:
        logger.debug("[factory] No cached API to shutdown")
        return

    logger.info("[factory] Shutting down API: %s", type(_api_instance).__name__)
    try:
        await _api_instance.shutdown()
    except Exception as e:
        logger.error("[factory] Error during API shutdown: %s", e)
    finally:
        reset_api_cache()


def get_api_mode() -> str:
    return os.getenv("OSSS_API_MODE", "real").lower()


def set_api_mode(mode: str) -> None:
    m = mode.lower()
    if m not in ("real", "mock"):
        raise ValueError(f"Invalid API mode: {mode}. Must be 'real' or 'mock'")
    os.environ["OSSS_API_MODE"] = m
    logger.info("[factory] Set API mode to: %s", m)


def is_mock_mode() -> bool:
    return get_api_mode() == "mock"


def get_cached_api_info() -> Optional[Dict[str, Any]]:
    global _api_instance
    if _api_instance is None:
        return None
    return {
        "class_name": type(_api_instance).__name__,
        "api_name": getattr(_api_instance, "api_name", None),
        "api_version": getattr(_api_instance, "api_version", None),
        "initialized": getattr(_api_instance, "_initialized", False),
        "mode": get_api_mode(),
    }


async def clear_orchestration_cache() -> Dict[str, Any]:
    """
    Clear orchestration-level caches (e.g., compiled LangGraph graphs).

    Intended to be called by the /admin/cache/clear (or similar) route.

    Behavior:
    - Ensures the orchestration API is initialized
    - If the API exposes `clear_graph_cache`, delegates to it
    - Otherwise, falls back to `reset_api_cache()` so the next call rebuilds
      a fresh API/graph state.
    """
    api = await get_orchestration_api()
    info: Dict[str, Any] = {
        "api_class": type(api).__name__,
        "mode": get_api_mode(),
    }

    clear_fn = getattr(api, "clear_graph_cache", None)

    if clear_fn is None:
        logger.warning(
            "[factory] Orchestration API does not expose clear_graph_cache; "
            "falling back to reset_api_cache",
            extra=info,
        )
        reset_api_cache()
        return {
            "status": "ok",
            "source": "factory",
            "action": "reset_api_cache",
            **info,
        }

    logger.info("[factory] Clearing orchestration graph cache via API", extra=info)

    try:
        if asyncio.iscoroutinefunction(clear_fn):
            result = await clear_fn()
        else:
            result = clear_fn()
    except Exception as e:
        logger.exception(
            "[factory] Error while clearing orchestration cache",
            extra={**info, "error": str(e)},
        )
        return {
            "status": "error",
            "error": str(e),
            **info,
        }

    payload: Dict[str, Any]
    if isinstance(result, dict):
        payload = result
    else:
        payload = {"detail": str(result)}

    return {
        "status": "ok",
        "source": "api",
        **info,
        **payload,
    }


class TemporaryAPIMode:
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
