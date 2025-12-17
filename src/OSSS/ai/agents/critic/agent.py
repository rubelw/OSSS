# ---------------------------------------------------------------------------
# Core agent framework imports
# ---------------------------------------------------------------------------
import asyncio
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
from OSSS.ai.utils.llm_text import coerce_llm_text

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

    def _wrap_output(
            self,
            output: str | None = None,
            *,
            intent: str | None = None,
            tone: str | None = None,
            action: str | None = None,
            sub_tone: str | None = None,
            content: str | None = None,  # legacy alias
            **_: Any,
    ) -> dict:
        return super()._wrap_output(
            output=output,
            intent=intent,
            tone=tone,
            action=action,
            sub_tone=sub_tone,
            content=content,
        )

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
            selected_model = (self.structured_service.model_name or "")
            if "llama" in selected_model.lower():
                self.logger.info(
                    f"[{self.name}] Disabling structured output for llama models (speed + reliability)"
                )
                self.structured_service = None

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

    async def _run_traditional(
            self,
            refined_output: str,
            system_prompt: str,
            context: AgentContext,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Critique the refined query below and suggest improvements.\n\n"
                    f"{refined_output}"
                ),
            },
        ]

        if hasattr(self.llm, "ainvoke"):
            response = await self.llm.ainvoke(messages)
        else:
            prompt_text = messages[-1]["content"]
            response = await asyncio.to_thread(self.llm.generate, prompt_text)

        return coerce_llm_text(response).strip()

    def _render_structured_critique(self, result: CriticOutput) -> str:
        """
        Convert CriticOutput -> readable text. Keeps the structured schema internal
        while producing a stable string for downstream consumers.
        """
        critique_lines: list[str] = []

        issues = getattr(result, "issues_identified", None) or []
        improvements = getattr(result, "suggested_improvements", None) or []
        rewritten = getattr(result, "rewritten_query", None)

        if issues:
            critique_lines.append("Issues identified:")
            critique_lines.extend([f"- {x}" for x in issues])

        if improvements:
            if critique_lines:
                critique_lines.append("")
            critique_lines.append("Suggested improvements:")
            critique_lines.extend([f"- {x}" for x in improvements])

        if rewritten:
            if critique_lines:
                critique_lines.append("")
            critique_lines.append("Improved query:")
            critique_lines.append(rewritten)

        # If the model returned an empty structure, avoid returning blank
        return ("\n".join(critique_lines)).strip() or "No critique generated."

    async def _run_structured(
            self,
            refined_output: str,
            system_prompt: str,
            context: AgentContext,
    ) -> str:
        """
        Structured critique using LangChainService + CriticOutput schema.
        Hard timeout enforced here to avoid hanging LLM calls.
        """

        if not self.structured_service:
            raise RuntimeError("Structured service not initialized")

        prompt = (
            "Critique the refined query below.\n\n"
            f"{refined_output}\n\n"
            "Return structured feedback according to the schema."
        )

        try:
            # NOTE: Your LangChainService.get_structured_output() does NOT accept
            # correlation_id (per your logs), so do not pass it.
            result = await asyncio.wait_for(
                self.structured_service.get_structured_output(
                    output_class=CriticOutput,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    include_raw=False,
                ),
                timeout=self.config.execution_config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"[{self.name}] Structured output timed out after "
                f"{self.config.execution_config.timeout_seconds}s"
            )
            raise  # caller falls back to traditional
        except TypeError as e:
            # If LangChainService signature drifts, make it obvious and recoverable
            self.logger.warning(
                f"[{self.name}] Structured output call signature mismatch: {e}"
            )
            raise  # caller falls back to traditional



        # Defensive: if service returns dict/model/None, normalize to CriticOutput-ish handling
        if result is None:
            return "No critique generated."

        from OSSS.ai.services.langchain_service import StructuredOutputResult

        if isinstance(result, StructuredOutputResult):
            result = result.parsed

        # If the service returns a dict, attempt to hydrate CriticOutput
        if isinstance(result, dict):
            try:
                result = CriticOutput(**result)
            except Exception:
                # Fall back to best-effort stringification
                return str(result).strip() or "No critique generated."

        # If it's already a CriticOutput, render it
        if isinstance(result, CriticOutput):
            return self._render_structured_critique(result)

        # Last resort: stringify unknown shapes
        return str(result).strip() or "No critique generated."

    def _normalize_llm_text(self, resp: Any) -> str:
        """
        Normalize different LLM response shapes to plain text.
        Prevents leaking response objects into AgentContext and downstream prompts.
        """
        content = (
            resp.content if hasattr(resp, "content")
            else resp.text if hasattr(resp, "text")
            else (resp.get("content") if isinstance(resp, dict) and "content" in resp else None)
        )
        return str(content if content is not None else resp).strip()

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

        # ✅ Always store plain text in context (never objects)
        critique_text = coerce_llm_text(critique).strip()

        env = self._wrap_output(
            output=critique_text,
            intent="critique_query",
            tone="neutral",
            action="read",
            sub_tone=None,
        )

        context.add_agent_output(self.name, critique_text)
        context.add_agent_output_envelope(self.name, env)

        context.log_trace(
            self.name,
            input_data=refined_output,
            output_data=critique_text,
        )

        return context