# ---------------------------------------------------------------------------
# Core agent framework imports
# ---------------------------------------------------------------------------

from OSSS.ai.agents.base_agent import (
    BaseAgent,           # Base class for all OSSS agents
    NodeType,            # Enum describing LangGraph node roles
    NodeInputSchema,     # Declarative input schema for graph validation
    NodeOutputSchema,    # Declarative output schema for graph validation
)
from OSSS.ai.context import AgentContext  # Shared execution context between agents
from OSSS.ai.llm.llm_interface import LLMInterface  # Abstract LLM interface

# Default (legacy) system prompt for critic behavior
from OSSS.ai.agents.critic.prompts import CRITIC_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Configuration & prompt composition
# ---------------------------------------------------------------------------

from typing import Optional, cast, Type
from OSSS.ai.config.agent_configs import CriticConfig  # Pydantic-based agent config
from OSSS.ai.workflows.prompt_composer import (
    PromptComposer,     # Responsible for building dynamic prompts
    ComposedPrompt,     # Validated prompt bundle (system + instructions)
)

# ---------------------------------------------------------------------------
# Structured output support via LangChain service abstraction
# ---------------------------------------------------------------------------

from OSSS.ai.services.langchain_service import LangChainService

# Strongly-typed structured output models
from OSSS.ai.agents.models import (
    CriticOutput,       # Pydantic model returned by structured LLM calls
    ProcessingMode,
    ConfidenceLevel,
)

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import asyncio
import logging
from typing import Dict, Any

# Global application configuration access
from OSSS.ai.config.app_config import get_config


class CriticAgent(BaseAgent):
    """
    Agent responsible for critiquing the output of the RefinerAgent.

    The CriticAgent evaluates the refined query produced by the RefinerAgent
    and provides structured, constructive feedback aimed at improving:
    - clarity
    - correctness
    - ambiguity
    - missing context

    Whenever possible, the agent uses *structured LLM output* to prevent
    hallucinations, schema drift, and output pollution.

    Attributes
    ----------
    name : str
        Agent identifier used in AgentContext and LangGraph.
    llm : LLMInterface
        Language model interface used for critique generation.
    config : CriticConfig
        Agent configuration controlling prompt depth, retries, and timeout.
    logger : logging.Logger
        Logger instance for traceability and debugging.
    """

    # Module-level logger shared across instances
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        llm: LLMInterface,
        config: Optional[CriticConfig] = None,
    ) -> None:
        """
        Initialize the CriticAgent.

        This constructor is intentionally lightweight and backward-compatible:
        existing callers that do not provide a config continue to work unchanged.

        Parameters
        ----------
        llm : LLMInterface
            Language model used to generate critiques.
        config : Optional[CriticConfig]
            Optional configuration object controlling agent behavior.
        """

        # -------------------------------------------------------------------
        # Configuration handling (backward compatible)
        # -------------------------------------------------------------------

        # If no config is provided, fall back to defaults defined in CriticConfig
        self.config = config if config is not None else CriticConfig()

        # Initialize BaseAgent with configured timeout
        super().__init__(
            name="critic",
            timeout_seconds=self.config.execution_config.timeout_seconds,
        )

        # Store LLM interface
        self.llm = llm

        # Prompt composer builds system + instruction prompts dynamically
        self._prompt_composer = PromptComposer()

        # Cached composed prompt (built once, reused per run)
        self._composed_prompt: Optional[ComposedPrompt] = None

        # Structured output service (LangChain-backed)
        self.structured_service: Optional[LangChainService] = None
        self._setup_structured_service()

        # Compose prompts eagerly for performance and early failure detection
        self._update_composed_prompt()

    def _setup_structured_service(self) -> None:
        """
        Initialize LangChain-based structured output service.

        This enables:
        - Pydantic-validated LLM responses
        - Better retry behavior
        - Output schema enforcement
        """
        try:
            # Attempt to extract API key from LLM interface (if present)
            api_key = getattr(self.llm, "api_key", None)

            # Let discovery logic select the most appropriate model
            self.structured_service = LangChainService(
                model=None,                 # Auto-select model
                api_key=api_key,
                temperature=0.0,            # Deterministic critiques
                agent_name="critic",        # Agent-specific model selection
                use_discovery=True,         # Enable discovery service
            )

            # Log selected model for observability
            selected_model = self.structured_service.model_name
            self.logger.info(
                f"[{self.name}] Structured output service initialized with model: {selected_model}"
            )

        except Exception as e:
            # Failure here is non-fatal; fallback to traditional LLM calls
            self.logger.warning(
                f"[{self.name}] Failed to initialize structured service: {e}. "
                f"Will use traditional LLM interface only."
            )
            self.structured_service = None

    def _update_composed_prompt(self) -> None:
        """
        Rebuild the composed prompt based on current configuration.

        This allows runtime configuration updates without restarting
        the agent or process.
        """
        try:
            self._composed_prompt = self._prompt_composer.compose_critic_prompt(
                self.config
            )
            self.logger.debug(
                f"[{self.name}] Prompt composed with analysis depth: {self.config.analysis_depth}"
            )
        except Exception as e:
            # Prompt composition failures should not break execution
            self.logger.warning(
                f"[{self.name}] Failed to compose prompt, using default: {e}"
            )
            self._composed_prompt = None

    def _get_system_prompt(self) -> str:
        """
        Resolve the system prompt to use for critique generation.

        Preference order:
        1. Valid composed prompt (config-driven)
        2. Static default system prompt (legacy fallback)
        """
        if (
            self._composed_prompt
            and self._prompt_composer.validate_composition(self._composed_prompt)
        ):
            return self._composed_prompt.system_prompt

        self.logger.debug(f"[{self.name}] Using default system prompt (fallback)")
        return CRITIC_SYSTEM_PROMPT

    def update_config(self, config: CriticConfig) -> None:
        """
        Update agent configuration at runtime.

        Automatically recomposes prompts to reflect new settings.
        """
        self.config = config
        self._update_composed_prompt()
        self.logger.info(
            f"[{self.name}] Configuration updated: {config.analysis_depth} analysis"
        )

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Execute the CriticAgent.

        This method:
        - Retrieves RefinerAgent output
        - Generates critique via structured or traditional LLM
        - Records trace and token usage
        - Writes output back into AgentContext
        """
        # Optional artificial delay (used for simulation/testing)
        config = get_config()
        if config.execution.enable_simulation_delay:
            await asyncio.sleep(config.execution.simulation_delay_seconds)

        self.logger.info(f"[{self.name}] Processing query: {context.query}")

        # Retrieve refined output produced by RefinerAgent
        refined_output = context.agent_outputs.get("refiner", "")

        if not refined_output:
            # Defensive handling when dependency output is missing
            critique = "No refined output available from RefinerAgent to critique."
            self.logger.warning(
                f"[{self.name}] No refined output available to critique."
            )
        else:
            self.logger.debug(
                f"[{self.name}] Analyzing refined query: {refined_output}"
            )

            system_prompt = self._get_system_prompt()

            # Prefer structured output when available
            if self.structured_service:
                try:
                    critique = await self._run_structured(
                        refined_output, system_prompt, context
                    )
                except Exception as e:
                    # Structured output failures are recoverable
                    self.logger.warning(
                        f"[{self.name}] Structured output failed, falling back to traditional: {e}"
                    )
                    critique = await self._run_traditional(
                        refined_output, system_prompt, context
                    )
            else:
                critique = await self._run_traditional(
                    refined_output, system_prompt, context
                )

        self.logger.debug(f"[{self.name}] Generated critique: {critique}")

        # Persist output and trace information
        context.add_agent_output(self.name, critique)
        context.log_trace(
            self.name,
            input_data=refined_output,
            output_data=critique,
        )

        return context
