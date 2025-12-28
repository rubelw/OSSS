from OSSS.ai.agents.base_agent import (
    BaseAgent,
    NodeType,
    NodeInputSchema,
    NodeOutputSchema,
)
import json
from OSSS.ai.context import AgentContext
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.config.app_config import get_config
from .prompts import REFINER_SYSTEM_PROMPT, DCG_CANONICALIZATION_BLOCK

# Structured output imports
from OSSS.ai.agents.models import RefinerOutput, ProcessingMode, ConfidenceLevel
from OSSS.ai.services.langchain_service import LangChainService

# Configuration system imports
from typing import Optional, Union
from OSSS.ai.config.agent_configs import RefinerConfig
from OSSS.ai.workflows.prompt_composer import PromptComposer, ComposedPrompt
from OSSS.ai.utils.llm_text import coerce_llm_text
from OSSS.ai.api.external import CompletionRequest

import logging
import asyncio
from typing import Dict, Any

# External API import
from OSSS.ai.api.external import LangGraphOrchestrationAPI

logger = logging.getLogger(__name__)


class RefinerAgent(BaseAgent):
    """
    Agent responsible for transforming raw user queries into structured, clarified prompts.
    """

    def __init__(self, llm: LLMInterface, config: Optional[RefinerConfig] = None) -> None:
        """
        Initialize the RefinerAgent with LLM interface and optional configuration.
        """
        self.config = config if config else RefinerConfig()

        super().__init__("refiner", timeout_seconds=self.config.execution_config.timeout_seconds)

        self.llm = llm
        self.structured_service = None
        if getattr(self.config, "use_structured_output", False):
            self._setup_structured_service()

        self._prompt_composer = PromptComposer()
        self._composed_prompt = None

        self._update_composed_prompt()

        self.orchestration_api = LangGraphOrchestrationAPI()

        logger.debug(f"[{self.name}] RefinerAgent initialized with config: {self.config}")

    def _inject_dcg_rule(self, system_prompt: str) -> str:
        if not isinstance(system_prompt, str):
            return system_prompt
        if "Dallas Center-Grimes School District" in system_prompt or "ABSOLUTE CANONICALIZATION RULE" in system_prompt:
            return system_prompt
        marker = "## PRIMARY RESPONSIBILITIES"
        if marker in system_prompt:
            return system_prompt.replace(
                marker,
                DCG_CANONICALIZATION_BLOCK + "\n\n" + marker,
                1,
            )
        return system_prompt.rstrip() + "\n\n" + DCG_CANONICALIZATION_BLOCK + "\n"

    def _setup_structured_service(self) -> None:
        try:
            api_key = getattr(self.llm, "api_key", None)
            self.structured_service = LangChainService(
                model=None,
                api_key=api_key,
                temperature=0.1,
                agent_name="refiner",
                use_discovery=True,
            )
            selected_model = self.structured_service.model_name
            logger.info(f"[{self.name}] Structured output service initialized with model: {selected_model}")
        except Exception as e:
            logger.warning(f"[{self.name}] Could not initialize structured output service: {e}")
            self.structured_service = None

    def _update_composed_prompt(self) -> None:
        try:
            composed = self._prompt_composer.compose_refiner_prompt(self.config)
            if composed and getattr(composed, "system_prompt", None):
                injected = self._inject_dcg_rule(composed.system_prompt)
                if hasattr(composed, "model_copy"):
                    composed = composed.model_copy(update={"system_prompt": injected})
                else:
                    setattr(composed, "system_prompt", injected)
            self._composed_prompt = composed
            logger.debug(f"[{self.name}] Prompt composed with config: {self.config.refinement_level}")
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to compose prompt, using default: {e}")
            self._composed_prompt = None

    def _get_system_prompt(self) -> str:
        """
        Return the canonical system prompt for the RefinerAgent.

        We intentionally bypass PromptComposer here to guarantee that the model
        always sees the strict JSON-output instructions defined in
        REFINER_SYSTEM_PROMPT.
        """
        logger.debug(f"[{self.name}] Using canonical REFINER_SYSTEM_PROMPT")
        return self._inject_dcg_rule(REFINER_SYSTEM_PROMPT)

    def _get_refiner_prompt(self, query: str) -> str:
        """
        Deprecated helper: left as a thin wrapper to keep callsites simple
        if needed, but we now rely on the system prompt to fully specify
        output format.

        The user message just provides the original query.
        """
        return f"Original query: {query}\n\nPlease refine this query according to the system instructions."

    def update_config(self, config: RefinerConfig) -> None:
        self.config = config
        self._update_composed_prompt()
        logger.info(f"[{self.name}] Configuration updated: {config.refinement_level} refinement")





    async def run(self, context: AgentContext) -> AgentContext:
        query = (context.query or "").strip()
        logger.info(f"[{self.name}] Processing query: {query}")

        # Retrieve task and cognitive classifications
        task_classification = context.get_task_classification()
        cognitive_classification = context.get_cognitive_classification()

        # Log task and cognitive classifications
        logger.debug(f"[{self.name}] Task Classification: {task_classification}")
        logger.debug(f"[{self.name}] Cognitive Classification: {cognitive_classification}")

        # Check for empty or malformed queries
        if not query:
            logger.error(f"[{self.name}] Received an empty or malformed query.")
            query = "Please provide a valid question to refine."

        exec_state = getattr(context, "execution_state", None)
        if not isinstance(exec_state, dict):
            exec_state = {}
            setattr(context, "execution_state", exec_state)
        exec_state.setdefault("original_query", query)

        system_prompt = self._get_system_prompt()

        # If orchestrator already injected RAG into execution_state, ensure flags are set
        if isinstance(context.execution_state, dict):
            rag_snippet = (
                    context.execution_state.get("rag_snippet")
                    or context.execution_state.get("rag_context")
                    or ""
            )
            if rag_snippet:
                context.execution_state["rag_snippet"] = rag_snippet
                context.execution_state["rag_snippet_present"] = True
                logger.info(f"[{self.name}] Using existing RAG snippet for query: {query[:100]}...")
            else:
                context.execution_state.setdefault("rag_snippet_present", False)

        # Structured service handling
        if self.structured_service:
            try:
                refined_output = await self._run_structured(query, system_prompt, context)
            except Exception as e:
                logger.warning(f"[{self.name}] Structured output failed, falling back to traditional: {e}")
                refined_output = await self._run_traditional(query, system_prompt, context)
        else:
            refined_output = await self._run_traditional(query, system_prompt, context)

        # Coerce LLM output to plain text
        raw_text = coerce_llm_text(refined_output).strip()
        if not raw_text:
            logger.error(f"[{self.name}] Refined output is empty; falling back to original query.")
            refined_query = query
        else:
            refined_query = None

            try:
                obj = json.loads(raw_text)
                rq = obj.get("refined_query")
                if isinstance(rq, str) and rq.strip():
                    refined_query = rq.strip()
                    logger.debug(f"[{self.name}] Parsed refined_query from JSON: {refined_query}")
            except json.JSONDecodeError:
                logger.warning(f"[{self.name}] Refiner output not valid JSON; falling back")

            if refined_query is None:
                if raw_text.startswith("[Unchanged]"):
                    candidate = raw_text[len("[Unchanged]"):].strip()
                    refined_query = candidate or query
                    logger.debug(f"[{self.name}] Using fallback [Unchanged] pattern: {refined_query}")
                else:
                    refined_query = raw_text
                    logger.debug(f"[{self.name}] Using raw_text as refined_query fallback: {refined_query}")

        # Ensure that refined query is added to the context
        context.execution_state["refined_query"] = refined_query

        final_agent_context = context  # Pass updated context to the final agent

        env = self._wrap_output(
            output=refined_query,
            intent="refine_query",
            tone="neutral",
            action="read",
            sub_tone=None,
        )

        context.add_agent_output(self.name, refined_query)
        context.add_agent_output_envelope(self.name, env)

        context.log_trace(self.name, input_data=query, output_data=refined_query)
        return context

    async def _run_structured(self, query: str, system_prompt: str, context: AgentContext) -> str:
        """Run with structured output using LangChain service."""
        import time

        start_time = time.time()

        if not self.structured_service:
            raise ValueError("Structured service not available")

        try:
            prompt = f"Original query: {query}\n\nPlease refine this query according to the system instructions."

            result = await self.structured_service.get_structured_output(
                prompt=prompt,
                output_class=RefinerOutput,
                system_prompt=system_prompt,
                max_retries=3,
            )

            if isinstance(result, RefinerOutput):
                structured_result = result
            else:
                from OSSS.ai.services.langchain_service import StructuredOutputResult

                if isinstance(result, StructuredOutputResult):
                    parsed_result = result.parsed
                    if not isinstance(parsed_result, RefinerOutput):
                        raise ValueError(f"Expected RefinerOutput, got {type(parsed_result)}")
                    structured_result = parsed_result
                else:
                    raise ValueError(f"Unexpected result type: {type(result)}")

            processing_time_ms = (time.time() - start_time) * 1000

            if structured_result.processing_time_ms is None:
                structured_result = structured_result.model_copy(
                    update={"processing_time_ms": processing_time_ms}
                )
                logger.info(f"[{self.name}] Injected server-calculated processing_time_ms: {processing_time_ms:.1f}ms")

            if "structured_outputs" not in context.execution_state:
                context.execution_state["structured_outputs"] = {}
            context.execution_state["structured_outputs"][self.name] = structured_result.model_dump()

            if not hasattr(context, "execution_metadata") or not isinstance(context.execution_metadata, dict):
                context.execution_metadata = {}

            context.execution_metadata.setdefault("agent_outputs", {})
            context.execution_metadata["agent_outputs"][self.name] = structured_result.model_dump()

            return structured_result.refined_query if not structured_result.was_unchanged else "[Unchanged] " + structured_result.refined_query

        except Exception as e:
            logger.debug(f"[{self.name}] Structured failed fast, falling back: {e}")
            raise

    async def _run_traditional(self, query: str, system_prompt: str, context: AgentContext) -> str:
        logger.info(f"[{self.name}] Using traditional LLM interface")

        user_prompt = self._get_refiner_prompt(query)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = await self.llm.ainvoke(messages)

        refined_query = coerce_llm_text(resp).strip()

        input_tokens = getattr(resp, "input_tokens", 0) or 0
        output_tokens = getattr(resp, "output_tokens", 0) or 0
        total_tokens = getattr(resp, "tokens_used", 0) or 0

        context.add_agent_token_usage(
            agent_name=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        if refined_query.startswith("[Unchanged]"):
            return refined_query
        return refined_query

    def define_node_metadata(self) -> Dict[str, Any]:
        return {
            "node_type": NodeType.PROCESSOR,
            "dependencies": [],
            "description": "Transforms raw user queries into structured, clarified prompts",
            "inputs": [
                NodeInputSchema(
                    name="context",
                    description="Agent context containing raw user query to refine",
                    required=True,
                    type_hint="AgentContext",
                )
            ],
            "outputs": [
                NodeOutputSchema(
                    name="context",
                    description="Updated context with refined query added",
                    type_hint="AgentContext",
                )
            ],
            "tags": ["refiner", "agent", "processor", "entry_point"],
        }
