# llm/factory.py

from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.llm.stub import StubLLM
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.provider_enum import LLMProvider

import os
from typing import Optional, Dict, Any


class LLMFactory:
    @staticmethod
    def create(
        llm_name: Optional[LLMProvider] = None,
        *,
        agent_name: Optional[str] = None,
        execution_config: Optional[Dict[str, Any]] = None,
    ) -> LLMInterface:
        """
        Create an LLM implementation.

        Added:
        - agent_name: lets callers request agent-specific LLM routing
        - execution_config: allows runtime overrides (e.g., critic model)

        Example usage (Critic agent):
            llm = LLMFactory.create(agent_name="critic", execution_config=config.get("execution_config"))

        Agent overrides supported via execution_config:
            - critic_llm
            - historian_llm
            - synthesis_llm

        Each may contain:
            { "provider": "ollama|openai|stub", "model": "...", "base_url": "...", "api_key": "...", ... }
        """
        execution_config = execution_config or {}
        if not isinstance(execution_config, dict):
            execution_config = {}

        # ------------------------------------------------------------------
        # Agent-specific overrides (highest priority)
        # ------------------------------------------------------------------
        agent = (agent_name or "").strip().lower()
        if agent in {"critic", "historian", "synthesis"}:
            cfg_key = f"{agent}_llm"
            agent_cfg = execution_config.get(cfg_key, {})
            if not isinstance(agent_cfg, dict):
                agent_cfg = {}

            provider_env = os.getenv(f"OSSS_{agent.upper()}_LLM_PROVIDER")
            provider_raw = (
                (agent_cfg.get("provider") or provider_env or "ollama").strip().lower()
            )

            # Default models per agent (all can be overridden via execution_config)
            if agent == "critic":
                default_model = os.getenv("OSSS_CRITIC_OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"
            elif agent == "historian":
                default_model = os.getenv("OSSS_HISTORIAN_OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"
            else:  # synthesis
                default_model = os.getenv("OSSS_SYNTHESIS_OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"

            model = agent_cfg.get("model") or default_model

            # Ollama is OpenAI-compatible at /v1/chat/completions, so reuse OpenAIChatLLM.
            if provider_raw == "ollama":
                base_url = (
                    agent_cfg.get("base_url")
                    or os.getenv("OSSS_OLLAMA_BASE_URL")
                    or "http://localhost:11434"
                )

                # NOTE: if OSSS runs in Docker and Ollama runs on the host,
                # set OSSS_OLLAMA_BASE_URL to:
                #   http://host.containers.internal:11434
                return OpenAIChatLLM(
                    api_key=agent_cfg.get("api_key")
                    or os.getenv("OSSS_OLLAMA_API_KEY")
                    or "ollama",
                    model=model,
                    base_url=base_url,
                )

            if provider_raw == "openai":
                config = OpenAIConfig.load()
                model = agent_cfg.get("model") or config.model
                return OpenAIChatLLM(
                    api_key=config.api_key,
                    model=model,
                    base_url=config.base_url,
                )

            if provider_raw == "stub":
                return StubLLM()

            raise ValueError(f"Unsupported {agent} provider: {provider_raw}")

        # ------------------------------------------------------------------
        # Default factory behavior (existing logic)
        # ------------------------------------------------------------------
        llm_name = llm_name or LLMProvider(os.getenv("OSSS_LLM", "openai").lower())

        if llm_name == LLMProvider.OPENAI:
            config = OpenAIConfig.load()
            return OpenAIChatLLM(
                api_key=config.api_key,
                model=config.model,
                base_url=config.base_url,
            )
        elif llm_name == LLMProvider.STUB:
            return StubLLM()
        else:
            raise ValueError(f"Unsupported LLM type: {llm_name}")
