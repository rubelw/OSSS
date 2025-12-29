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
from typing import Optional, Any, Dict
from OSSS.ai.config.agent_configs import RefinerConfig
from OSSS.ai.workflows.prompt_composer import PromptComposer
from OSSS.ai.utils.llm_text import coerce_llm_text  # still imported if you use it elsewhere
from OSSS.ai.api.external import CompletionRequest

import logging
import asyncio

# External API import (currently unused here, but kept if you plan to use it later)
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
        User message content for the refiner call.
        """
        return f"Original query: {query}\n\nPlease refine this query according to the system instructions."

    def update_config(self, config: RefinerConfig) -> None:
        self.config = config
        self._update_composed_prompt()
        logger.info(f"[{self.name}] Configuration updated: {config.refinement_level} refinement")

    # --- classification helpers -----------------------------------------
    def _coerce_task_classification_value(self, value: Any) -> Optional[str]:
        """
        Normalize task_classification from context into a simple string.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            intent = value.get("intent") or value.get("label") or value.get("task")
            if isinstance(intent, str) and intent.strip():
                return intent.strip()
        try:
            text = str(value).strip()
            return text or None
        except Exception:
            return None

    def _coerce_cognitive_classification_value(self, value: Any) -> Optional[str]:
        """
        Normalize cognitive_classification from context into a simple string.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            domain = value.get("domain")
            topic = value.get("topic")
            parts = []
            if isinstance(domain, str) and domain.strip():
                parts.append(domain.strip())
            if isinstance(topic, str) and topic.strip():
                parts.append(topic.strip())
            if parts:
                return " : ".join(parts)
        try:
            text = str(value).strip()
            return text or None
        except Exception:
            return None

    async def _run_structured(self, query: str, system_prompt: str, context: AgentContext) -> str:
        """Run with structured output using LangChain service."""
        import time

        start_time = time.time()

        if not self.structured_service:
            raise ValueError("Structured service not available")

        try:
            prompt = self._get_refiner_prompt(query)

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

            # Inject classifier signals from context into RefinerOutput
            try:
                task_raw = context.get_task_classification()
                cognitive_raw = context.get_cognitive_classification()

                task_str = self._coerce_task_classification_value(task_raw)
                cognitive_str = self._coerce_cognitive_classification_value(cognitive_raw)

                if task_str is not None or cognitive_str is not None:
                    structured_result = structured_result.model_copy(
                        update={
                            "task_classification": task_str or structured_result.task_classification,
                            "cognitive_classification": cognitive_str or structured_result.cognitive_classification,
                        }
                    )
                    logger.debug(
                        f"[{self.name}] Injected classifier metadata into RefinerOutput",
                        extra={
                            "task_classification": task_str,
                            "cognitive_classification": cognitive_str,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"[{self.name}] Failed to inject classifier metadata into RefinerOutput: {e}"
                )

            processing_time_ms = (time.time() - start_time) * 1000

            if structured_result.processing_time_ms is None:
                structured_result = structured_result.model_copy(
                    update={"processing_time_ms": processing_time_ms}
                )
                logger.info(f"[{self.name}] Injected server-calculated processing_time_ms: {processing_time_ms:.1f}ms")

            if not hasattr(context, "execution_state") or not isinstance(context.execution_state, dict):
                context.execution_state = {}

            if "structured_outputs" not in context.execution_state:
                context.execution_state["structured_outputs"] = {}
            context.execution_state["structured_outputs"][self.name] = structured_result.model_dump()

            if not hasattr(context, "execution_metadata") or not isinstance(context.execution_metadata, dict):
                context.execution_metadata = {}

            context.execution_metadata.setdefault("agent_outputs", {})
            context.execution_metadata["agent_outputs"][self.name] = structured_result.model_dump()

            return (
                structured_result.refined_query
                if not structured_result.was_unchanged
                else "[Unchanged] " + structured_result.refined_query
            )

        except Exception as e:
            logger.debug(f"[{self.name}] Structured failed fast, falling back: {e}")
            raise

    # ----------------------------------------------------------------------
    # Helper: normalize LLM response -> refined_query string (JSON-aware)
    # ----------------------------------------------------------------------
    def _extract_refined_query_from_llm_response(self, resp: Any) -> str:
        """
        Extract the 'refined_query' string from an LLM response without ever
        calling `.strip()` on a dict.

        Handles:
        - OpenAI-style resp.choices[0].message.content
        - Dict-based responses with the same structure
        - Already-parsed JSON objects with a `refined_query` field
        - Plain text responses that contain JSON
        """
        content: Any = None

        # 1) Try OpenAI-style object access
        try:
            if hasattr(resp, "choices"):
                choices = getattr(resp, "choices", None)
                if choices:
                    choice0 = choices[0]
                    message = getattr(choice0, "message", None) or getattr(choice0, "delta", None)
                    if isinstance(message, dict):
                        content = message.get("content")
                    else:
                        content = getattr(message, "content", None)
        except Exception:
            content = None  # don't let introspection failures blow things up

        # 2) Fallback: dict-style response
        if content is None and isinstance(resp, dict):
            try:
                if "choices" in resp:
                    choice0 = resp["choices"][0]
                    msg = choice0.get("message") or choice0.get("delta") or {}
                    content = msg.get("content")
                elif "content" in resp:
                    content = resp["content"]
            except Exception:
                content = None

        # 3) Last resort: use the whole response object
        if content is None:
            content = resp

        # If it's already a dict, treat as parsed JSON
        if isinstance(content, dict):
            rq = content.get("refined_query")
            if isinstance(rq, str):
                return rq.strip()
            # Fall back to stringified content
            return str(content)

        # Treat as text from here
        text = str(content).strip()

        # Try to interpret the text as JSON of the form {"refined_query": "..."}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                rq = parsed.get("refined_query")
                if isinstance(rq, str):
                    return rq.strip()
        except Exception:
            # Not valid JSON – just use raw text
            pass

        return text

    async def _run_traditional(self, query: str, system_prompt: str, context: AgentContext) -> str:
        logger.info(f"[{self.name}] Using traditional LLM interface")

        user_prompt = self._get_refiner_prompt(query)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = await self.llm.ainvoke(messages)

        # JSON-aware extraction of the "refined_query" field or fallback text
        refined_query = self._extract_refined_query_from_llm_response(resp)

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

    def _extract_query_text(self, context: AgentContext) -> str:
        """
        Robustly extract a string query from the AgentContext.
        """
        raw: Any = None

        # Preferred source: context.get_user_question()
        try:
            raw = context.get_user_question()
        except Exception as e:
            logger.debug(f"[{self.name}] get_user_question() failed: {e}")

        # Fallback: context.query
        if not raw:
            raw = getattr(context, "query", None)

        # If it's already a string, normalize and return
        if isinstance(raw, str):
            return raw.strip()

        # If it's a dict, try common text-bearing keys first
        if isinstance(raw, dict):
            for key in ("query", "text", "content", "message"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            # Last resort: JSON-encode the dict to a string
            try:
                return json.dumps(raw, ensure_ascii=False).strip()
            except Exception:
                return ""

        # Other types (list, numbers, etc.) – stringify defensively
        if raw is not None:
            try:
                return str(raw).strip()
            except Exception:
                return ""

        return ""

    async def run(self, context: AgentContext, **kwargs: Any) -> AgentContext:
        """
        Concrete implementation of the abstract BaseAgent.run.

        Picks structured vs traditional mode, updates execution_state, and
        records an AgentOutputEnvelope in the context.
        """
        # Get the best version of the user query, robust to non-string types
        query = self._extract_query_text(context)

        system_prompt = self._get_system_prompt()

        use_structured = bool(
            getattr(self.config, "use_structured_output", False) and self.structured_service
        )
        processing_mode = "structured" if use_structured else "traditional"

        if use_structured:
            try:
                refined_query = await self._run_structured(query, system_prompt, context)
            except Exception as e:
                logger.warning(
                    "[%s] Structured mode failed, falling back to traditional: %s",
                    self.name,
                    e,
                )
                processing_mode = "traditional"
                refined_query = await self._run_traditional(query, system_prompt, context)
        else:
            refined_query = await self._run_traditional(query, system_prompt, context)

        # Store results in execution_state for downstream agents
        if not hasattr(context, "execution_state") or not isinstance(context.execution_state, dict):
            context.execution_state = {}

        context.execution_state.setdefault("refiner", {})
        context.execution_state["refiner"].update(
            {
                "original_query": query,
                "refined_query": refined_query,
                "processing_mode": processing_mode,
            }
        )
        # Simple top-level key for convenience
        context.execution_state["refined_query"] = refined_query

        # Build meta payload
        meta: Dict[str, Any] = {
            "processing_mode": processing_mode,
            "agent": self.name,
            "original_query": query,
        }
        try:
            meta["task_classification"] = context.get_task_classification()
            meta["cognitive_classification"] = context.get_cognitive_classification()
        except Exception:
            # non-fatal – just skip if helpers blow up
            pass

        # Attach structured output snapshot if present
        try:
            structured_outputs = context.execution_state.get("structured_outputs", {})
            if isinstance(structured_outputs, dict) and self.name in structured_outputs:
                meta["structured_output"] = structured_outputs[self.name]
        except Exception:
            pass

        # Record canonical envelope – NOTE: content is a STRING, not a dict.
        context.add_agent_output(
            agent_name=self.name,
            logical_name="refiner",
            content=refined_query,
            role="assistant",
            action="refine",
            intent="informational",
            meta=meta,
        )

        return context

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
