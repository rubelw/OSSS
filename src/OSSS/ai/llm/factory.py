from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.llm.stub import StubLLM
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.provider_enum import LLMProvider
from OSSS.ai.observability import get_logger  # Ensure you import the logger from the observability module

import os
from typing import Optional

# Initialize the logger from observability
logger = get_logger(__name__)


class LLMFactory:
    @staticmethod
    def create(llm_name: Optional[LLMProvider] = None) -> LLMInterface:
        # Get the LLM provider name from the environment or use the default
        llm_name = llm_name or LLMProvider(os.getenv("OSSS_LLM", "openai").lower())

        # Log the LLM creation attempt and configuration
        logger.debug(f"Creating LLM with name: {llm_name}")

        # Check which LLM provider to create
        if llm_name == LLMProvider.OPENAI:
            try:
                # Load OpenAI configuration
                logger.debug("Loading OpenAIConfig...")
                config = OpenAIConfig.load()
                logger.debug(f"OpenAIConfig loaded successfully. Using model: {config.model}")

                # Create and return the OpenAI LLM instance
                llm_instance = OpenAIChatLLM(
                    api_key=config.api_key,
                    model=config.model,
                    base_url=config.base_url,
                )
                logger.info(f"OpenAI LLM instance created successfully with model: {config.model}")
                return llm_instance

            except Exception as e:
                logger.error(f"Failed to load OpenAI configuration or create LLM: {e}")
                raise

        elif llm_name == LLMProvider.STUB:
            logger.debug("Creating StubLLM instance...")
            llm_instance = StubLLM()
            logger.info("StubLLM instance created successfully.")
            return llm_instance

        else:
            # Raise an error if an unsupported LLM provider is requested
            logger.error(f"Unsupported LLM provider: {llm_name}")
            raise ValueError(f"Unsupported LLM type: {llm_name}")
