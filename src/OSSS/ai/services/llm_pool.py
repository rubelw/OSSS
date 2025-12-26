"""
LLM Service Pool - Eliminates redundant LLM service creation and client pooling.

This addresses the architectural redundancy where each agent creates its own:
- LangChainService instance
- ModelDiscoveryService instance
- ChatOpenAI client instance

Instead, provides:
- Single model discovery per workflow
- Shared ChatOpenAI clients by model
- Thread-safe service caching
- Async-safe initialization
"""

import asyncio
import threading
from typing import Dict, Optional, Any, List
import os
from dotenv import load_dotenv, find_dotenv

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from OSSS.ai.observability import get_logger
from OSSS.ai.services.model_discovery_service import ModelDiscoveryService, ModelInfo

# Load environment variables
load_dotenv(find_dotenv(), override=True)

logger = get_logger("services.llm_pool")


class LLMServicePool:
    """
    Singleton pool that manages shared LLM services and clients.

    Eliminates redundancy by:
    - Single model discovery per workflow (not per agent)
    - Shared ChatOpenAI clients by model configuration
    - Centralized LLM configuration management
    - Thread-safe service caching
    """

    _instance: Optional["LLMServicePool"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._discovery_service: Optional[ModelDiscoveryService] = None
        self._llm_clients: Dict[str, BaseChatModel] = {}  # model -> client
        self._discovered_models: Optional[List[ModelInfo]] = None
        self._initialized = False
        self._api_key = os.getenv("OPENAI_API_KEY")

        # Metrics
        self.metrics = {
            "discovery_calls": 0,
            "clients_created": 0,
            "clients_reused": 0,
            "agents_served": 0,
        }

    @classmethod
    def get_instance(cls) -> "LLMServicePool":
        """Get or create singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("Created new LLMServicePool singleton instance")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for testing)."""
        with cls._lock:
            if cls._instance:
                logger.info("Resetting LLMServicePool instance")
            cls._instance = None

    async def initialize_if_needed(self) -> None:
        """Initialize discovery service once per workflow."""
        if self._initialized:
            return

        logger.info("Initializing LLMServicePool with model discovery...")

        try:
            # Create discovery service once
            self._discovery_service = ModelDiscoveryService(
                api_key=self._api_key, enable_discovery=True, fallback_on_error=True
            )

            # Discover models once
            self._discovered_models = await self._discovery_service.discover_models()
            self.metrics["discovery_calls"] += 1

            logger.info(
                f"LLMServicePool initialized with {len(self._discovered_models)} models"
            )
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize LLMServicePool: {e}")
            # Continue with fallback behavior
            self._initialized = True

    async def get_model_for_agent(self, agent_name: str) -> str:
        """
        Get the best model for an agent using shared discovery service.

        This replaces the redundant per-agent model selection.
        """
        await self.initialize_if_needed()

        if self._discovery_service:
            try:
                best_model = await self._discovery_service.get_best_model_for_agent(
                    agent_name
                )
                if best_model:
                    logger.info(
                        f"Selected {best_model} for {agent_name} (via pooled discovery)"
                    )
                    return best_model
            except Exception as e:
                logger.warning(f"Pooled model selection failed for {agent_name}: {e}")

        # Fallback to agent-specific defaults
        fallback_models = {
            "refiner": "gpt-4o-mini",
            "historian": "gpt-4o",
            "critic": "gpt-4o-mini",
            "synthesis": "gpt-4o",
        }

        fallback = fallback_models.get(agent_name, "gpt-4o")
        logger.info(f"Using fallback model {fallback} for {agent_name}")
        return fallback

    def get_or_create_client(
            self,
            model: str,
            temperature: float = 0.1,
            *,
            max_tokens: Optional[int] = None,
            request_timeout: float = 30.0,
    ) -> BaseChatModel:
        model_lower = model.lower()

        # --- ADD IT HERE (compute once) ---
        base_url = os.getenv("OPENAI_BASE_URL")  # ollama or real openai
        if base_url:
            logger.info(f"LLMServicePool using base_url={base_url}")

        is_ollama = bool(base_url) and "11434" in base_url

        # Ollama defaults (only if caller didn't override)
        if is_ollama:
            if max_tokens is None:
                max_tokens = 200
            request_timeout = min(request_timeout, 12.0)
        # --- END ADDITION ---

        # llama3.1 temperature rule
        if "llama3.1" in model_lower:
            effective_temperature = None
            temp_key = "default"
        else:
            effective_temperature = temperature
            temp_key = f"{temperature}"

        mt_key = str(max_tokens) if max_tokens is not None else "none"
        to_key = str(request_timeout)
        bu_key = base_url or "none"

        # IMPORTANT: cache key must include everything that changes client behavior
        client_key = f"{model}@temp={temp_key}@max={mt_key}@to={to_key}@base={bu_key}"

        if client_key in self._llm_clients:
            self.metrics["clients_reused"] += 1
            logger.debug(f"Reusing cached client for {client_key}")
            return self._llm_clients[client_key]

        logger.info(f"Creating new ChatOpenAI client for {client_key}")

        kwargs: Dict[str, Any] = {
            "model": model,
            "api_key": self._api_key,
            "max_retries": 3,
            "request_timeout": request_timeout,
        }

        if base_url:
            kwargs["base_url"] = base_url

        if effective_temperature is not None:
            kwargs["temperature"] = effective_temperature

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        client = ChatOpenAI(**kwargs)
        self._llm_clients[client_key] = client
        self.metrics["clients_created"] += 1
        return client

    async def get_optimal_client_for_agent(
            self, agent_name: str, temperature: Optional[float] = None
    ) -> tuple[BaseChatModel, str]:

        model = await self.get_model_for_agent(agent_name)

        if temperature is None:
            temperature_defaults = {
                "refiner": 0.1,
                "historian": 0.3,
                "critic": 0.0,
                "synthesis": 0.2,
            }
            temperature = temperature_defaults.get(agent_name, 0.1)

        # ---- PER-AGENT max_tokens cap ----
        max_tokens = 600 if agent_name == "synthesis" else 300

        client = self.get_or_create_client(
            model,
            temperature,
            max_tokens=max_tokens,
            request_timeout=12.0,  # if you want the same “hard timeout” behavior
        )

        self.metrics["agents_served"] += 1
        return client, model

    def get_metrics(self) -> Dict[str, Any]:
        """Get pool metrics for monitoring."""
        total_client_ops = (
            self.metrics["clients_created"] + self.metrics["clients_reused"]
        )

        return {
            **self.metrics,
            "client_reuse_rate": (
                self.metrics["clients_reused"] / total_client_ops
                if total_client_ops > 0
                else 0.0
            ),
            "pool_size": len(self._llm_clients),
            "discovered_models": (
                len(self._discovered_models) if self._discovered_models else 0
            ),
            "initialized": self._initialized,
        }

    def cleanup(self) -> None:
        """Clean up resources (for testing/shutdown)."""
        logger.info("Cleaning up LLMServicePool resources")
        self._llm_clients.clear()
        self._discovered_models = None
        self._discovery_service = None
        self._initialized = False

        # Reset metrics
        for key in self.metrics:
            self.metrics[key] = 0


# Convenience functions
async def get_pooled_client_for_agent(
    agent_name: str, temperature: Optional[float] = None
) -> tuple[BaseChatModel, str]:
    """
    Convenience function to get optimal client for an agent.

    Usage in agents:
        client, model = await get_pooled_client_for_agent("refiner")
    """
    pool = LLMServicePool.get_instance()
    return await pool.get_optimal_client_for_agent(agent_name, temperature)


def get_pool_metrics() -> Dict[str, Any]:
    """Get current pool metrics."""
    pool = LLMServicePool.get_instance()
    return pool.get_metrics()