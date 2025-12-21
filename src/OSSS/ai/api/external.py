"""
External API contracts for OSSS.

These APIs form the stable interface that external consumers depend on.

Key points about this module:
- It defines *contracts* (interfaces / abstract-ish base classes), not implementations.
- External callers should code against these contracts, not internal orchestrator classes.
- Any breaking change to these signatures or semantics requires:
  1) a migration path
  2) an API version bump
- Concrete implementations live elsewhere (e.g., LangGraphOrchestrationAPI).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import importlib
import warnings
from typing import List, Dict, Any, Optional, Type

# ---------------------------------------------------------------------------
# Local package imports (API infrastructure)
# ---------------------------------------------------------------------------

from .base import BaseAPI
from .decorators import ensure_initialized

# ---------------------------------------------------------------------------
# Local package imports (request/response models)
# ---------------------------------------------------------------------------

from .models import (
    WorkflowRequest,
    WorkflowResponse,
    StatusResponse,
    CompletionRequest,
    CompletionResponse,
    LLMProviderInfo,
)


class OrchestrationAPI(BaseAPI):
    """
    Public orchestration API - STABLE INTERFACE.
    """

    @property
    def api_name(self) -> str:
        return "Orchestration API"

    @property
    def api_version(self) -> str:
        return "1.0.0"

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        raise NotImplementedError("Subclasses must implement execute_workflow")

    @ensure_initialized
    async def get_status(self, workflow_id: str) -> StatusResponse:
        raise NotImplementedError("Subclasses must implement get_status")

    @ensure_initialized
    async def cancel_workflow(self, workflow_id: str) -> bool:
        raise NotImplementedError("Subclasses must implement cancel_workflow")

    def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError("Subclasses must implement get_workflow_history")

    async def get_workflow_history_from_database(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "Subclasses must implement get_workflow_history_from_database"
        )

    @ensure_initialized
    async def get_status_by_correlation_id(self, correlation_id: str) -> StatusResponse:
        raise NotImplementedError(
            "Subclasses must implement get_status_by_correlation_id"
        )


class LLMGatewayAPI(BaseAPI):
    """
    LLM Gateway API - Future service extraction boundary.

    ⚠️ IMPORTANT: THIS API IS NOT YET IMPLEMENTED ⚠️
    """

    @property
    def api_name(self) -> str:
        return "LLM Gateway API"

    @property
    def api_version(self) -> str:
        return "1.0.0"

    @ensure_initialized
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        warnings.warn(
            "LLMGatewayAPI.complete() is not implemented. This is a placeholder for future LLM gateway service. "
            "Use OSSS.ai.llm.OpenAIChatLLM or similar classes for current LLM functionality.",
            UserWarning,
            stacklevel=2,
        )
        raise NotImplementedError(
            "LLMGatewayAPI.complete() is not yet implemented - this is a future placeholder"
        )

    @ensure_initialized
    async def get_providers(self) -> List[LLMProviderInfo]:
        warnings.warn(
            "LLMGatewayAPI.get_providers() is not implemented. This is a placeholder for future LLM gateway service.",
            UserWarning,
            stacklevel=2,
        )
        raise NotImplementedError(
            "LLMGatewayAPI.get_providers() is not yet implemented - this is a future placeholder"
        )

    @ensure_initialized
    async def estimate_cost(self, request: CompletionRequest) -> Dict[str, float]:
        warnings.warn(
            "LLMGatewayAPI.estimate_cost() is not implemented. This is a placeholder for future LLM gateway service.",
            UserWarning,
            stacklevel=2,
        )
        raise NotImplementedError(
            "LLMGatewayAPI.estimate_cost() is not yet implemented - this is a future placeholder"
        )


# ---------------------------------------------------------------------------
# Concrete orchestration implementation (best-effort import, NO import-time crash)
# ---------------------------------------------------------------------------

# If your concrete implementation moves, add its module path here.
# Keep this list short and explicit.
_LANGGRAPH_IMPL_CANDIDATES = [
    # Most likely locations (adjust/add as needed)
    "OSSS.ai.api.langgraph",                       # e.g. OSSS/ai/api/langgraph.py
    "OSSS.ai.api.langgraph_api",                   # e.g. OSSS/ai/api/langgraph_api.py
    "OSSS.ai.api.orchestration_langgraph",         # e.g. OSSS/ai/api/orchestration_langgraph.py
    "OSSS.ai.api.impl.langgraph_orchestration",    # e.g. OSSS/ai/api/impl/langgraph_orchestration.py
    "OSSS.ai.api.external_impl",                   # e.g. OSSS/ai/api/external_impl.py
    "OSSS.ai.api.langgraph_orchestration_api",     # e.g. OSSS/ai/api/langgraph_orchestration_api.py
]


def _resolve_langgraph_api_class() -> Type[Any]:
    """
    Try to locate LangGraphOrchestrationAPI without crashing module import.
    """
    for module_path in _LANGGRAPH_IMPL_CANDIDATES:
        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError:
            continue

        cls = getattr(mod, "LangGraphOrchestrationAPI", None)
        if cls is not None:
            return cls

    raise ImportError(
        "LangGraphOrchestrationAPI could not be located. "
        "Update OSSS.ai.api.external._LANGGRAPH_IMPL_CANDIDATES to include the module "
        "that defines `class LangGraphOrchestrationAPI`."
    )


class LangGraphOrchestrationAPI:  # type: ignore[misc]
    """
    Proxy symbol to preserve the existing import style:

        from OSSS.ai.api.external import LangGraphOrchestrationAPI

    Resolution is deferred so external.py never hard-crashes app startup.
    """

    def __new__(cls, *args: Any, **kwargs: Any):
        real_cls = _resolve_langgraph_api_class()
        return real_cls(*args, **kwargs)


__all__ = [
    "OrchestrationAPI",
    "LLMGatewayAPI",
    "LangGraphOrchestrationAPI",
]
