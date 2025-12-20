import json
import asyncio
from typing import Type, TypeVar, Optional, Dict, Any, Union, cast, List
from pydantic import BaseModel, ValidationError

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser

from OSSS.ai.observability import get_logger, get_observability_context
from OSSS.ai.exceptions import LLMError, LLMValidationError
from OSSS.ai.services.model_discovery_service import (
    get_model_discovery_service,
    ModelDiscoveryService,
    ModelCategory,
    ModelSpeed,
)

MAX_STRUCTURED_ATTEMPTS = 1

# Import pool for eliminating redundancy
try:
    from OSSS.ai.services.llm_pool import LLMServicePool

    POOL_AVAILABLE = True
except ImportError:
    POOL_AVAILABLE = False


T = TypeVar("T", bound=BaseModel)


class StructuredOutputResult:
    """Wrapper for structured output with debugging info."""

    def __init__(
        self,
        parsed: BaseModel,
        raw: Optional[str] = None,
        method_used: Optional[str] = None,
        fallback_used: bool = False,
        processing_time_ms: Optional[float] = None,
    ):
        self.parsed = parsed
        self.raw = raw
        self.method_used = method_used
        self.fallback_used = fallback_used
        self.processing_time_ms = processing_time_ms


class LangChainService:
    """
    LangChain service with structured output capabilities.

    Implements patterns from the LangChain structured output article:
    - Uses with_structured_output() as primary method
    - Provider-specific optimizations (json_schema, function_calling, etc.)
    - Fallback to PydanticOutputParser for models that don't support structured output
    - Rich validation and error handling
    - Dynamic model discovery and intelligent selection
    """

    # Provider-specific method mapping - SIMPLIFIED for base models
    PROVIDER_METHODS = {
        "llama3.1": "json_schema",  # Base llama3.1 has full json_schema support
        "llama3.1-mini": "json_schema",  # Mini is still a base model, keep it
        "llama3.1-nano": "json_schema",  # Nano is still a base model, keep it
        "gpt-4o": "json_schema",  # GPT-4o supports json_schema
        "gpt-4o-mini": "json_schema",  # GPT-4o-mini supports json_schema
        "gpt-4-turbo": "json_schema",  # GPT-4-turbo supports json_schema
        "gpt-4": "function_calling",  # GPT-4 does NOT support json_schema
        "gpt-3.5": "function_calling",
        "claude-3": "function_calling",
        "claude-2": "function_calling",
        "gemini": "json_mode",
        "llama": "json_mode",
        "mistral": "json_mode",
    }

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        agent_name: Optional[str] = None,
        use_discovery: bool = True,
        use_pool: bool = True,  # NEW: Use pool when available
    ):
        """
        Initialize LangChain service with model.

        Args:
            model: Model name (if None, uses discovery service or pool)
            temperature: Model temperature
            api_key: OpenAI API key
            base_url: Optional base URL for API
            agent_name: Agent name for model selection (e.g., "refiner")
            use_discovery: Whether to use model discovery service
            use_pool: Whether to use the LLMServicePool (eliminates redundancy)
        """
        self.logger = get_logger("services.langchain")
        self.agent_name = agent_name
        self.use_discovery = use_discovery
        self.use_pool = use_pool and POOL_AVAILABLE
        self.api_key = api_key
        self.temperature = temperature
        self.base_url = base_url  # used for provider detection (ollama vs openai)

        # Type declarations for pool client
        self._pool_client: Optional[BaseChatModel] = None
        self._use_pool_client = False
        self.llm: Optional[BaseChatModel] = None

        # Try to use pool first (eliminates redundancy)
        if self.use_pool and self.agent_name and not model:
            try:
                self.logger.info(f"Using LLMServicePool for {self.agent_name}")
                pool = LLMServicePool.get_instance()

                # Use async-safe method to get client (will be called later)
                self._use_pool_client = True
                self.model_name = (
                    "pooled"  # Temporary, will be set when client is created
                )

            except Exception as e:
                self.logger.warning(f"Could not use LLMServicePool: {e}, falling back")
                self._use_pool_client = False
        else:
            self._use_pool_client = False

        # Fallback to original logic if not using pool
        if not self._use_pool_client:
            # Initialize model discovery service if enabled
            self.discovery_service: Optional[ModelDiscoveryService] = None
            if use_discovery:
                try:
                    self.discovery_service = get_model_discovery_service(
                        api_key=api_key
                    )
                except Exception as e:
                    self.logger.warning(f"Could not initialize discovery service: {e}")

            # Determine model to use
            self.model_name = model or self._select_best_model()
            self.logger.info(
                f"Using model: {self.model_name} for agent: {agent_name or 'default'}"
            )

            # Create appropriate LLM instance based on provider
            self.llm = self._create_llm_instance(
                self.model_name, temperature, api_key, base_url
            )

        # Metrics tracking with proper typing
        self.metrics: Dict[str, Union[int, str]] = {
            "total_calls": 0,
            "successful_structured": 0,
            "fallback_used": 0,
            "validation_failures": 0,
            "model_selected": (
                self.model_name if hasattr(self, "model_name") else "unknown"
            ),
        }

    def _json_instruction(self, output_class: Type[BaseModel]) -> str:
        """
        Strict JSON-only instruction for prompted JSON mode.

        Key goals:
        - Exact top-level keys only (no nesting like {"Refined Query": {...}})
        - No extra keys
        - No renaming (case-sensitive)
        - Strong “shape” example to anchor the model
        """
        schema = output_class.model_json_schema()
        keys = list(output_class.model_fields.keys())
        keys_str = ", ".join(keys)

        # Build an "example shape" that doesn't accidentally force invalid nulls.
        # If a field is optional/nullable in schema, show null; otherwise show a plausible placeholder.
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}

        def _placeholder_for(k: str) -> str:
            p = props.get(k, {})
            # nullable if anyOf includes {"type":"null"} OR type == "null"
            nullable = False
            if isinstance(p, dict):
                anyof = p.get("anyOf")
                if isinstance(anyof, list):
                    nullable = any(isinstance(x, dict) and x.get("type") == "null" for x in anyof)
                if p.get("type") == "null":
                    nullable = True

            if nullable:
                return "null"

            # simple placeholders to reduce model “creativity”
            if isinstance(p, dict) and p.get("type") == "array":
                return "[]"
            if isinstance(p, dict) and p.get("type") == "object":
                return "{}"
            if isinstance(p, dict) and p.get("type") == "number":
                return "0"
            if isinstance(p, dict) and p.get("type") == "boolean":
                return "false"

            # default string-ish placeholder
            return "\"\""

        example_lines = [f'  "{k}": {_placeholder_for(k)},' for k in keys]
        example = "{\n" + "\n".join(example_lines) + "\n}\n"

        return (
            "Return ONLY valid JSON (no markdown, no commentary).\n"
            f"Top-level keys MUST be exactly: {keys_str}\n"
            "Do NOT rename keys. Do NOT nest under other keys. Do NOT add extra keys.\n"
            "Values must match the schema types.\n"
            "Example shape (keys only):\n"
            f"{example}"
        )

    async def _ensure_pooled_client(self) -> None:
        """Ensure pooled client is initialized (async-safe)."""
        if self._use_pool_client and not self._pool_client:
            try:
                pool = LLMServicePool.get_instance()
                if self.agent_name:  # Type guard
                    (
                        self._pool_client,
                        self.model_name,
                    ) = await pool.get_optimal_client_for_agent(
                        self.agent_name, self.temperature
                    )
                    self.llm = self._pool_client
                else:
                    raise ValueError("agent_name is required for pooled client")
                self.logger.info(
                    f"Initialized pooled client: {self.model_name} for {self.agent_name}"
                )
            except Exception as e:
                self.logger.error(f"Failed to get pooled client: {e}")
                # Fallback to traditional client creation
                self._use_pool_client = False
                self.model_name = self._select_best_model()
                self.llm = self._create_llm_instance(
                    self.model_name, self.temperature, self.api_key, None
                )

    def _select_best_model(self) -> str:
        """Select the best available model using discovery service."""
        if not self.discovery_service or not self.agent_name:
            # Default fallback
            return "gpt-4o"

        try:
            # Check if we're already in an async context
            import asyncio

            try:
                # Try to get the current running loop
                loop = asyncio.get_running_loop()
                # We're in an async context, can't use run_until_complete
                # Use sync fallback for now
                self.logger.info(
                    f"In async context, using fallback model selection for '{self.agent_name}'"
                )
            except RuntimeError:
                # No running loop, we can create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    best_model = loop.run_until_complete(
                        self.discovery_service.get_best_model_for_agent(self.agent_name)
                    )
                    if best_model:
                        self.logger.info(
                            f"Discovery service selected '{best_model}' for agent '{self.agent_name}'"
                        )
                        return best_model
                finally:
                    loop.close()
        except Exception as e:
            self.logger.warning(f"Model discovery failed: {e}")

        # SIMPLIFIED fallbacks - prefer base llama3.1 when available
        # User wisdom: "just use the model: 'llama3.1'"
        agent_fallbacks = {
            "refiner": "llama3.1",  # Keep nano for ultra-fast requirement
            "historian": "llama3.1",  # Base llama3.1 for historian
            "critic": "llama3.1",  # Base llama3.1 for critic
            "synthesis": "llama3.1",  # Base llama3.1 for synthesis
        }
        fallback = agent_fallbacks.get(self.agent_name, "gpt-4o")
        self.logger.info(
            f"Using fallback model '{fallback}' for agent '{self.agent_name}'"
        )
        return fallback
