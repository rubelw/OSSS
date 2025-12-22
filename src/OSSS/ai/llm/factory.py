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

        Agent overrides supported via execution_config:
            - critic_llm
            - refiner_llm
            - historian_llm
            - synthesis_llm

        Each may contain:
            {
              "provider": "ollama|openai|stub|gateway",
              "model": "...",
              "base_url": "...",
              "api_key": "...",
              "extra_body": { ... }   # <= NEW: top-level JSON fields merged into request body
            }
        """
        execution_config = execution_config or {}
        if not isinstance(execution_config, dict):
            execution_config = {}

        agent = (agent_name or "").strip().lower()
        if agent in {"critic", "refiner", "historian", "synthesis"}:
            cfg_key = f"{agent}_llm"
            agent_cfg = execution_config.get(cfg_key, {})
            if not isinstance(agent_cfg, dict):
                agent_cfg = {}

            provider_env = os.getenv(f"OSSS_{agent.upper()}_LLM_PROVIDER")

            # critic/refiner default to ollama; historian/synthesis default to gateway (RAG)
            default_provider = "ollama" if agent in {"critic", "refiner"} else "gateway"
            provider_raw = ((agent_cfg.get("provider") or provider_env or default_provider).strip().lower())

            # Default models:
            # - critic/refiner: qwen (cheap)
            # - historian/synthesis: llama3.1:latest (stronger) via gateway (RAG)
            if agent == "refiner":
                default_model = os.getenv("OSSS_REFINER_OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"
            elif agent == "critic":
                default_model = os.getenv("OSSS_CRITIC_OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"
            elif agent == "historian":
                default_model = os.getenv("OSSS_HISTORIAN_MODEL") or "llama3.1:latest"
            else:  # synthesis
                default_model = os.getenv("OSSS_SYNTHESIS_MODEL") or "llama3.1:latest"

            model = agent_cfg.get("model") or default_model

            # NEW: top-level request fields to merge into the OpenAI-compatible payload
            extra_body = agent_cfg.get("extra_body")
            if not isinstance(extra_body, dict):
                extra_body = {}

            # Force RAG on for historian+synthesis when using the gateway.
            if agent in {"historian", "synthesis"}:
                extra_body.setdefault("use_rag", True)
            else:
                extra_body.setdefault("use_rag", False)

            # ------------------------------------------------------------------
            # Providers
            # ------------------------------------------------------------------
            if provider_raw in {"gateway", "rag", "ai_gateway"}:
                base_url = (
                    agent_cfg.get("base_url")
                    or os.getenv("OSSS_AI_GATEWAY_BASE_URL")
                    or "http://localhost:8081"
                )
                base_url = base_url.rstrip("/")
                if not base_url.endswith("/v1"):
                    base_url = f"{base_url}/v1"

                return OpenAIChatLLM(
                    api_key=agent_cfg.get("api_key") or os.getenv("OSSS_AI_GATEWAY_API_KEY") or "gateway",
                    model=model,
                    base_url=base_url,
                    extra_body=extra_body,  # 👈 important
                )

            if provider_raw == "ollama":
                base_url = (
                    agent_cfg.get("base_url")
                    or os.getenv("OSSS_OLLAMA_BASE_URL")
                    or "http://host.containers.internal:11434"
                )
                base_url = base_url.rstrip("/")
                if not base_url.endswith("/v1"):
                    base_url = f"{base_url}/v1"

                return OpenAIChatLLM(
                    api_key=agent_cfg.get("api_key") or os.getenv("OSSS_OLLAMA_API_KEY") or "ollama",
                    model=model,
                    base_url=base_url,
                    extra_body=extra_body,
                )

            if provider_raw == "openai":
                config = OpenAIConfig.load()
                model = agent_cfg.get("model") or config.model
                return OpenAIChatLLM(
                    api_key=config.api_key,
                    model=model,
                    base_url=config.base_url,
                    extra_body=extra_body,
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
