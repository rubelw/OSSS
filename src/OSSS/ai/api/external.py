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

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import warnings  # Used to emit explicit runtime warnings for placeholder APIs
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Local package imports (API infrastructure)
# ---------------------------------------------------------------------------

from .base import BaseAPI  # Base class providing shared lifecycle hooks and health/metrics patterns
from .decorators import ensure_initialized  # Guard that ensures initialize() has been called

# ---------------------------------------------------------------------------
# Local package imports (request/response models)
# ---------------------------------------------------------------------------

from .models import (
    WorkflowRequest,        # Request model for orchestrated multi-agent workflows
    WorkflowResponse,       # Response model containing workflow outputs and metadata
    StatusResponse,         # Status polling response (running/completed/failed, etc.)
    CompletionRequest,      # Request model for future LLM gateway completion API
    CompletionResponse,     # Response model for future LLM gateway completion API
    LLMProviderInfo,        # Provider/model metadata for future LLM gateway API
)


class OrchestrationAPI(BaseAPI):
    """
    Public orchestration API - STABLE INTERFACE.

    This contract is the primary boundary that external consumers depend on.

    Important design intent:
    - This class is a *contract* (interface), not a concrete implementation.
    - Subclasses must implement the actual behavior.
    - The methods are decorated with ensure_initialized to enforce lifecycle safety:
      implementations must be initialized before use (connections, caches, etc.).

    Backward compatibility rules:
    - Keep method names, parameters, and return models stable.
    - Avoid changing semantics of fields without migration.
    - Any breaking change requires version bump and migration strategy.
    """

    # -----------------------------------------------------------------------
    # API identity metadata
    # -----------------------------------------------------------------------

    @property
    def api_name(self) -> str:
        """Human-readable name for logs/health endpoints."""
        return "Orchestration API"

    @property
    def api_version(self) -> str:
        """Semantic-ish version string of this contract."""
        return "1.0.0"

    # -----------------------------------------------------------------------
    # Core orchestration operations
    # -----------------------------------------------------------------------

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Execute a workflow with specified agents.

        This is the central "do the work" entrypoint for orchestrating
        multiple agents as a single logical workflow.

        Args:
            request : WorkflowRequest
                Parameters describing:
                - query to execute
                - which agents to run (optional)
                - execution config (timeouts, metadata, etc.)
                - correlation_id for tracing (optional)
                - export options (optional)

        Returns:
            WorkflowResponse
                Contains:
                - workflow_id
                - status
                - agent_outputs
                - execution time metadata
                - correlation_id echo (if provided)

        Raises:
            ValueError:
                If request parameters are invalid (e.g., unsupported agent list)
            RuntimeError:
                If execution fails in a way the implementation chooses to surface
                as a hard failure rather than a "failed" WorkflowResponse
        """
        # This is an interface method: real implementations must override it.
        raise NotImplementedError("Subclasses must implement execute_workflow")

    @ensure_initialized
    async def get_status(self, workflow_id: str) -> StatusResponse:
        """
        Get workflow execution status.

        Typical usage:
        - Clients call execute_workflow to start work
        - Clients poll get_status(workflow_id) until completed/failed

        Args:
            workflow_id : str
                Unique workflow identifier returned by execute_workflow.

        Returns:
            StatusResponse
                Contains:
                - workflow status (running/completed/failed/cancelled/etc.)
                - progress estimates (if supported)
                - current agent (if supported)
                - estimated completion time (if supported)

        Raises:
            KeyError:
                If the workflow_id is not known to the implementation.
        """
        # NOTE: Message says execute_workflow, but the intent is get_status.
        # Keeping unchanged for backward compatibility with your original code.
        raise NotImplementedError("Subclasses must implement execute_workflow")

    @ensure_initialized
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.

        Cancellation semantics are implementation-defined:
        - Some implementations may support real cancellation.
        - Others may only "soft cancel" (mark cancelled, ignore results).

        Args:
            workflow_id : str
                Unique workflow identifier.

        Returns:
            bool
                True if cancellation was accepted,
                False if cancellation is not possible (already done, unknown, etc.).
        """
        raise NotImplementedError("Subclasses must implement cancel_workflow")

    # -----------------------------------------------------------------------
    # Workflow history operations
    # -----------------------------------------------------------------------

    def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent workflow execution history.

        This method is synchronous because the earliest implementations
        were in-memory and did not require async I/O.

        Args:
            limit : int
                Maximum number of results to return.

        Returns:
            List[Dict[str, Any]]
                A list of history entries (shape is implementation-defined but
                should remain stable per implementation).

        Note:
            Future implementations may prefer a database-backed async method,
            which is why get_workflow_history_from_database exists.
        """
        raise NotImplementedError("Subclasses must implement get_workflow_history")

    async def get_workflow_history_from_database(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get workflow history from database instead of in-memory storage.

        This method provides:
        - Durable history
        - Pagination (limit/offset)
        - More consistent results across process restarts

        Args:
            limit : int
                Maximum number of results to return.
            offset : int
                Number of results to skip (for pagination).

        Returns:
            List[Dict[str, Any]]
                History entries (implementation-defined structure).
        """
        raise NotImplementedError(
            "Subclasses must implement get_workflow_history_from_database"
        )

    # -----------------------------------------------------------------------
    # Convenience lookup operations
    # -----------------------------------------------------------------------

    @ensure_initialized
    async def get_status_by_correlation_id(self, correlation_id: str) -> StatusResponse:
        """
        Get workflow execution status by correlation_id.

        correlation_id is useful for:
        - end-to-end tracing across services
        - client-side idempotency keys
        - tracking requests without storing workflow_id externally

        Args:
            correlation_id : str
                Unique correlation identifier for the request.

        Returns:
            StatusResponse
                Current workflow status for the correlation ID.

        Raises:
            KeyError:
                If correlation_id is not found by the implementation.
        """
        raise NotImplementedError(
            "Subclasses must implement get_status_by_correlation_id"
        )


class LLMGatewayAPI(BaseAPI):
    """
    LLM Gateway API - Future service extraction boundary.

    ⚠️ IMPORTANT: THIS API IS NOT YET IMPLEMENTED ⚠️

    This class defines a *future contract* for an LLM gateway service.
    The intent is to eventually provide a stable microservice boundary for:
    - uniform completion requests across providers
    - provider discovery
    - cost estimation
    - policy enforcement / rate limiting

    Current status:
    - There are no implementations yet.
    - All methods raise NotImplementedError.
    - Calls emit warnings to make misuse obvious during development.

    Guidance:
    - For now, use existing LLM classes directly (e.g. OSSS.ai.llm.OpenAIChatLLM).
    """

    # -----------------------------------------------------------------------
    # API identity metadata
    # -----------------------------------------------------------------------

    @property
    def api_name(self) -> str:
        """Human-friendly name for future service boundary."""
        return "LLM Gateway API"

    @property
    def api_version(self) -> str:
        """Contract version for future gateway service."""
        return "1.0.0"

    # -----------------------------------------------------------------------
    # Placeholder methods (not implemented)
    # -----------------------------------------------------------------------

    @ensure_initialized
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Generate an LLM completion.

        ⚠️ NOT IMPLEMENTED ⚠️

        Intended future behavior:
        - Route completion request to configured provider/model
        - Normalize responses
        - Provide usage metrics + structured metadata

        Args:
            request : CompletionRequest
                Completion parameters (prompt, system prompt, model constraints, etc.)

        Returns:
            CompletionResponse
                Generated text + metadata (tokens, timings, provider/model info)

        Raises:
            NotImplementedError:
                Always raised until an implementation exists.
        """
        # Emit an explicit warning so developers see this is a placeholder boundary.
        warnings.warn(
            "LLMGatewayAPI.complete() is not implemented. This is a placeholder for future LLM gateway service. "
            "Use OSSS.ai.llm.OpenAIChatLLM or similar classes for current LLM functionality.",
            UserWarning,
            stacklevel=2,  # Points warning at the caller rather than inside this API
        )
        raise NotImplementedError(
            "LLMGatewayAPI.complete() is not yet implemented - this is a future placeholder"
        )

    @ensure_initialized
    async def get_providers(self) -> List[LLMProviderInfo]:
        """
        Get available LLM providers and models.

        ⚠️ NOT IMPLEMENTED ⚠️

        Intended future behavior:
        - Return provider inventory (OpenAI, Anthropic, local, etc.)
        - Return model capabilities (context length, tool support, pricing tiers)
        - Support discovery and selection strategies

        Returns:
            List[LLMProviderInfo]
                Structured list of available providers/models.

        Raises:
            NotImplementedError:
                Always raised until an implementation exists.
        """
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
        """
        Estimate completion cost across providers.

        ⚠️ NOT IMPLEMENTED ⚠️

        Intended future behavior:
        - Estimate cost for the same request across multiple providers
        - Consider prompt tokens, expected output tokens, and provider pricing
        - Return comparable cost breakdowns

        Args:
            request : CompletionRequest
                Completion parameters to evaluate for cost.

        Returns:
            Dict[str, float]
                Mapping of provider/model identifiers to estimated cost.

        Raises:
            NotImplementedError:
                Always raised until an implementation exists.
        """
        warnings.warn(
            "LLMGatewayAPI.estimate_cost() is not implemented. This is a placeholder for future LLM gateway service.",
            UserWarning,
            stacklevel=2,
        )
        raise NotImplementedError(
            "LLMGatewayAPI.estimate_cost() is not yet implemented - this is a future placeholder"
        )
