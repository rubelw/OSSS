from OSSS.ai.agents.base_agent import (
    BaseAgent,
    NodeType,
    NodeInputSchema,
    NodeOutputSchema,
)
import os
import json
from OSSS.ai.context import AgentContext
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.config.app_config import get_config
from .prompts import REFINER_SYSTEM_PROMPT, DCG_CANONICALIZATION_BLOCK

import joblib  # 👈 for joblib-style models

# Structured output imports
from OSSS.ai.agents.models import RefinerOutput, ProcessingMode, ConfidenceLevel
from OSSS.ai.services.langchain_service import LangChainService

# Configuration system imports
from typing import Optional, Any, Dict, Tuple
from OSSS.ai.config.agent_configs import RefinerConfig
from OSSS.ai.workflows.prompt_composer import PromptComposer
from OSSS.ai.utils.llm_text import coerce_llm_text  # still imported if you use it elsewhere
from OSSS.ai.api.external import CompletionRequest

import logging
import asyncio

# ✅ final refinement service
from OSSS.ai.services.final_refinement_service import (
    FinalRefinementService,
    FinalRefinementResult,
)

# ✅ NLP extraction service
from OSSS.ai.services.nlp_extraction_service import NLPExtractionService

# External API import (currently unused here, but kept if you plan to use it later)
from OSSS.ai.api.external import LangGraphOrchestrationAPI

logger = logging.getLogger(__name__)

# 👇 default on-disk model path (can be overridden by config or env)
DEFAULT_REFINER_MODEL_PATH = os.getenv(
    "OSSS_REFINER_MODEL_PATH",
    "/workspace/data_model/refiner/models/refiner_nn.joblib",
)


class RefinerAgent(BaseAgent):
    """
    Agent responsible for transforming raw user queries into structured, clarified prompts.

    Responsibilities:
    - Rewrite user input into a cleaner, explicit "refined_query".
    - Extract structured bits (entities, date_filters, flags).
    - Store results in execution_state for downstream agents.

    It does NOT:
    - Decide which agents or graph patterns to use.
    - Perform routing or planning.
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

        # ✅ optional joblib-backed lightweight refiner
        self._joblib_model = None

        # 1) Prefer explicit config override if present
        cfg_path = getattr(self.config, "joblib_model_path", None)

        # 2) Fall back to default path (can also be overridden via OSSS_REFINER_MODEL_PATH)
        model_path = cfg_path or DEFAULT_REFINER_MODEL_PATH

        if model_path:
            try:
                if not os.path.exists(model_path):
                    logger.warning(
                        "[%s] Joblib refiner model path does not exist: %s",
                        self.name,
                        model_path,
                    )
                else:
                    self._joblib_model = joblib.load(model_path)
                    logger.info(
                        "[%s] Loaded joblib refiner model from %s",
                        self.name,
                        model_path,
                    )
            except Exception as e:
                logger.warning(
                    "[%s] Failed to load joblib refiner model from %s: %s",
                    self.name,
                    model_path,
                    e,
                )
                self._joblib_model = None

        # ✅ NLP extraction service (best-effort, non-LLM)
        enable_nlp = getattr(self.config, "enable_nlp_extraction", True)
        self._nlp_service: Optional[NLPExtractionService] = NLPExtractionService(
            enabled=enable_nlp,
            model_name=getattr(self.config, "nlp_model_name", "en_core_web_sm"),
        )

        # ✅ ALWAYS define final refinement service attribute so run() can't crash
        enable_final_refinement = getattr(self.config, "enable_final_refinement", True)
        if enable_final_refinement:
            self._final_refinement_service: Optional[FinalRefinementService] = FinalRefinementService(
                style_hint="clear, concise, helpful for school staff and admins",
                enabled=True,
            )
        else:
            self._final_refinement_service = None

        logger.debug(f"[{self.name}] RefinerAgent initialized with config: {self.config}")

    # --- cheap / heuristic refiner helpers ---------------------------------

    def _apply_cheap_rules(self, query: str) -> str:
        """
        Very fast, deterministic normalization that does not call an LLM.

        Examples:
        - Expand DCG to Dallas Center-Grimes School District.
        - Normalize whitespace.
        - Preserve leading CRUD verb 'query', 'create', etc.
        """
        if not query:
            return ""

        q = query.strip()

        # DCG canonicalization (same semantics as DCG_CANONICALIZATION_BLOCK)
        # but applied locally for cheap path.
        lower = q.lower()
        if "dcg" in lower:
            # naive but effective replacement; you can do smarter token-based replacement
            q = q.replace("DCG", "Dallas Center-Grimes School District")
            q = q.replace("dcg", "Dallas Center-Grimes School District")

        # Optional: ensure 'query ' prefix stays if present
        if lower.startswith("query "):
            # Already satisfied by preserving original string;
            # if you wanted, you could do more structure here.
            pass

        # Collapse excessive spaces
        while "  " in q:
            q = q.replace("  ", " ")

        return q

    def _joblib_refine(self, query: str) -> Optional[Tuple[str, float]]:
        """
        If a joblib-backed model is available, use it to produce a refined query.

        Returns (refined_query, confidence) or None if not applicable.
        """
        if not self._joblib_model or not query:
            return None

        try:
            # Your NearestNeighborRefiner returns a dict
            result = self._joblib_model.predict([query])[0]

            if isinstance(result, dict):
                rq = result.get("refined_query") or result.get("text")
                conf = float(result.get("confidence", 0.0))
                if isinstance(rq, str) and rq.strip():
                    return rq.strip(), conf
                return None

            # Fallback: model returns just a string; assume high confidence
            if isinstance(result, str) and result.strip():
                return result.strip(), 0.9

            return None
        except Exception as e:
            logger.warning(
                "[%s] joblib refiner failed; ignoring and falling back: %s",
                self.name,
                e,
            )
            return None

    def _cheap_refine(self, query: str) -> Tuple[str, float, bool]:
        """
        Run fast, non-LLM refinement and return:

        (refined_query, confidence, should_skip_llm)

        - confidence: 0.0–1.0 (rough notion of how 'safe' the cheap result is)
        - should_skip_llm: True if we decide not to call the LLM at all.
        """
        if not query:
            return "", 0.0, False

        q = query.strip()
        original = q

        # 1) apply deterministic rules
        q_rules = self._apply_cheap_rules(q)

        # 2) optionally apply joblib model
        joblib_result = self._joblib_refine(q_rules)
        if joblib_result is not None:
            refined_joblib, conf = joblib_result

            # Heuristic: if joblib is confident enough, and query is not too long,
            # we can safely skip LLM.
            max_len = getattr(self.config, "max_simple_length", 120)
            if conf >= 0.8 and len(q) <= max_len:
                return refined_joblib, conf, True

            # Otherwise, use it as a better starting point but still allow LLM
            return refined_joblib, conf, False

        # 3) no joblib; just rules
        # If rules didn't change anything, confidence is modest
        if q_rules == original:
            return q_rules, 0.4, False

        # If rules changed DCG or trimmed whitespace, that's usually safe
        return q_rules, 0.7, len(q) <= getattr(self.config, "max_simple_length", 120)

    # ----------------------------------------------------------------------
    # DCG injection + prompt plumbing
    # ----------------------------------------------------------------------
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
        return (
            f"Original query:\n{query}\n\n"
            "Please refine this query and emit ONLY the JSON object described in the system instructions."
        )

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

    # ----------------------------------------------------------------------
    # Structured mode: LangChain + RefinerOutput model
    # ----------------------------------------------------------------------
    async def _run_structured(
        self,
        query: str,
        system_prompt: str,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """
        Run with structured output using LangChain service and normalize to the
        canonical 4-key schema:
            {refined_query, entities, date_filters, flags}
        """
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

            # Inject classifier signals from context into RefinerOutput (if supported by model)
            try:
                task_raw = context.get_task_classification()
                cognitive_raw = context.get_cognitive_classification()

                task_str = self._coerce_task_classification_value(task_raw)
                cognitive_str = self._coerce_cognitive_classification_value(cognitive_raw)

                if task_str is not None or cognitive_str is not None:
                    structured_result = structured_result.model_copy(
                        update={
                            "task_classification": task_str or structured_result.task_classification,
                            "cognitive_classification": cognitive_str
                            or structured_result.cognitive_classification,
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

            if getattr(structured_result, "processing_time_ms", None) is None:
                structured_result = structured_result.model_copy(
                    update={"processing_time_ms": processing_time_ms}
                )
                logger.info(
                    f"[{self.name}] Injected server-calculated processing_time_ms: {processing_time_ms:.1f}ms"
                )

            # Persist structured result snapshot
            if not hasattr(context, "execution_state") or not isinstance(
                context.execution_state, dict
            ):
                context.execution_state = {}

            if "structured_outputs" not in context.execution_state:
                context.execution_state["structured_outputs"] = {}
            context.execution_state["structured_outputs"][self.name] = structured_result.model_dump()

            if not hasattr(context, "execution_metadata") or not isinstance(
                context.execution_metadata, dict
            ):
                context.execution_metadata = {}

            context.execution_metadata.setdefault("agent_outputs", {})
            context.execution_metadata["agent_outputs"][self.name] = structured_result.model_dump()

            # Normalize to the 4-key schema, duck-typing off the Pydantic model
            base = structured_result.model_dump()

            refined_query = (base.get("refined_query") or query).strip() or query
            entities = base.get("entities") or {}
            date_filters = base.get("date_filters") or {}
            flags = base.get("flags") or {}

            # Ensure correct types
            if not isinstance(entities, dict):
                entities = {}
            if not isinstance(date_filters, dict):
                date_filters = {}
            if not isinstance(flags, dict):
                flags = {}

            return {
                "refined_query": refined_query,
                "entities": entities,
                "date_filters": date_filters,
                "flags": flags,
            }

        except Exception as e:
            logger.debug(f"[{self.name}] Structured failed fast, falling back: {e}")
            raise

    # ----------------------------------------------------------------------
    # Helpers: normalize LLM response -> canonical schema
    # ----------------------------------------------------------------------
    def _normalize_refiner_obj(self, obj: Any, fallback_query: str) -> Dict[str, Any]:
        """
        Given an object (typically parsed JSON or a dict-like), coerce it into:

            {
              "refined_query": str,
              "entities": dict,
              "date_filters": dict,
              "flags": dict,
            }

        Tolerant of missing or malformed fields.
        """
        if not isinstance(obj, dict):
            obj = {}

        refined_query = obj.get("refined_query")
        if not isinstance(refined_query, str) or not refined_query.strip():
            refined_query = fallback_query

        entities = obj.get("entities") or {}
        date_filters = obj.get("date_filters") or {}
        flags = obj.get("flags") or {}

        if not isinstance(entities, dict):
            entities = {}
        if not isinstance(date_filters, dict):
            date_filters = {}
        if not isinstance(flags, dict):
            flags = {}

        return {
            "refined_query": refined_query.strip(),
            "entities": entities,
            "date_filters": date_filters,
            "flags": flags,
        }

    def _extract_refiner_obj_from_llm_response(
        self,
        resp: Any,
        fallback_query: str,
    ) -> Dict[str, Any]:
        """
        Extract the canonical refiner object from an LLM response.

        Handles:
        - OpenAI-style resp.choices[0].message.content
        - Dict-based responses
        - Already-parsed JSON objects
        - Plain text that contains JSON
        """
        content: Any = None

        # 1) Try OpenAI-style object access
        try:
            if hasattr(resp, "choices"):
                choices = getattr(resp, "choices", None)
                if choices:
                    choice0 = choices[0]
                    message = getattr(choice0, "message", None) or getattr(
                        choice0, "delta", None
                    )
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
            return self._normalize_refiner_obj(content, fallback_query=fallback_query)

        # Treat as text from here
        text = str(content).strip()

        # Try to interpret the text as JSON of the form
        # {"refined_query": "...", "entities": {...}, "date_filters": {...}, "flags": {...}}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return self._normalize_refiner_obj(parsed, fallback_query=fallback_query)
        except Exception:
            # Not valid JSON – fall through
            pass

        # Fallback: we at least have a string; use it as refined_query
        return {
            "refined_query": text or fallback_query,
            "entities": {},
            "date_filters": {},
            "flags": {},
        }

    # ----------------------------------------------------------------------
    # Traditional mode: plain LLM call that returns JSON text
    # ----------------------------------------------------------------------
    async def _run_traditional(
        self,
        query: str,
        system_prompt: str,
        context: AgentContext,
    ) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Using traditional LLM interface")

        user_prompt = self._get_refiner_prompt(query)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = await self.llm.ainvoke(messages)

        # Token accounting (if available)
        input_tokens = getattr(resp, "input_tokens", 0) or 0
        output_tokens = getattr(resp, "output_tokens", 0) or 0
        total_tokens = getattr(resp, "tokens_used", 0) or 0

        context.add_agent_token_usage(
            agent_name=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        # JSON-aware extraction of the canonical refiner object
        refiner_obj = self._extract_refiner_obj_from_llm_response(
            resp,
            fallback_query=query,
        )
        return refiner_obj

    # ----------------------------------------------------------------------
    # Query extraction from context
    # ----------------------------------------------------------------------
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

    # ----------------------------------------------------------------------
    # Main entrypoint
    # ----------------------------------------------------------------------
    async def run(self, context: AgentContext, **kwargs: Any) -> AgentContext:
        """
        Concrete implementation of the abstract BaseAgent.run.

        1) Use cheap/heuristic + optional joblib refiner.
        2) Only call the LLM (structured/traditional and final-refinement) if necessary.
        3) Optionally run NLP extractor.
        4) Store results in execution_state and record an AgentOutputEnvelope.
        """
        # Get the best version of the user query, robust to non-string types
        query = self._extract_query_text(context)

        system_prompt = self._get_system_prompt()

        use_structured = bool(
            getattr(self.config, "use_structured_output", False) and self.structured_service
        )
        processing_mode = "traditional"  # default; may be updated below

        # ------------------------------------------------------------------
        # 1) Cheap / heuristic refiner (no LLM)
        # ------------------------------------------------------------------
        cheap_refined, cheap_conf, skip_llm = ("", 0.0, False)
        if getattr(self.config, "enable_lightweight_refiner", True):
            cheap_refined, cheap_conf, skip_llm = self._cheap_refine(query)
            logger.info(
                "[%s] cheap_refiner result",
                self.name,
                extra={
                    "event": "refiner_cheap_result",
                    "cheap_refined_preview": cheap_refined[:200],
                    "cheap_confidence": cheap_conf,
                    "skip_llm": skip_llm,
                },
            )

        refined_query = cheap_refined or query

        # Prepare default structured bits
        entities: Dict[str, Any] = {}
        date_filters: Dict[str, Any] = {}
        flags: Dict[str, Any] = {}

        # ------------------------------------------------------------------
        # 2) Optional LLM-based refinement (structured or traditional)
        #    - Completely skipped when skip_llm == True
        # ------------------------------------------------------------------
        if skip_llm:
            processing_mode = "lightweight"
        else:
            if use_structured:
                try:
                    processing_mode = "structured"
                    refiner_obj = await self._run_structured(refined_query, system_prompt, context)
                except Exception as e:
                    logger.warning(
                        "[%s] Structured mode failed, falling back to traditional: %s",
                        self.name,
                        e,
                    )
                    processing_mode = "traditional"
                    refiner_obj = await self._run_traditional(refined_query, system_prompt, context)
            else:
                processing_mode = "traditional"
                refiner_obj = await self._run_traditional(refined_query, system_prompt, context)

            # structured/traditional return the canonical dict
            refined_query = refiner_obj.get("refined_query", refined_query)
            entities = refiner_obj.get("entities", {}) or {}
            date_filters = refiner_obj.get("date_filters", {}) or {}
            flags = refiner_obj.get("flags", {}) or {}

        # ------------------------------------------------------------------
        # 3) Optional NLP extraction (non-LLM) – augment entities/date_filters/flags
        # ------------------------------------------------------------------
        nlp_service = getattr(self, "_nlp_service", None)
        if nlp_service is not None:
            try:
                nlp_struct = nlp_service.extract(str(refined_query))
                nlp_entities = nlp_struct.get("entities") or {}
                nlp_dates = nlp_struct.get("date_filters") or {}
                nlp_flags = nlp_struct.get("flags") or {}

                if isinstance(entities, dict) and isinstance(nlp_entities, dict):
                    entities = {**entities, **nlp_entities}
                if isinstance(date_filters, dict) and isinstance(nlp_dates, dict):
                    date_filters = {**date_filters, **nlp_dates}
                if isinstance(flags, dict) and isinstance(nlp_flags, dict):
                    flags = {**flags, **nlp_flags}
            except Exception as e:
                logger.warning(
                    "[%s] NLPExtractionService.extract failed; continuing without NLP: %s",
                    self.name,
                    e,
                )

        # ------------------------------------------------------------------
        # 4) Optional final refinement service pass (LLM-based)
        #    - Also skipped entirely when skip_llm == True
        #    - Uses a trimmed execution_state preview to avoid huge prompts
        # ------------------------------------------------------------------
        refinement_result: Optional[FinalRefinementResult] = None
        service = getattr(self, "_final_refinement_service", None)

        if service is not None and not skip_llm:
            try:
                exec_preview: Any = getattr(context, "execution_state", {})
                if isinstance(exec_preview, dict):
                    # Shallow copy and trim large text fields
                    preview_copy: Dict[str, Any] = dict(exec_preview)
                    for k in ("rag_context", "rag_snippet"):
                        if k in preview_copy and isinstance(preview_copy[k], str):
                            val = preview_copy[k]
                            max_len = getattr(self.config, "final_refinement_preview_max_len", 500)
                            if len(val) > max_len:
                                preview_copy[k] = val[:max_len]
                    exec_preview = preview_copy

                refinement_result = await service.refine(
                    user_query=query,
                    original_answer=refined_query,
                    extra_context={
                        "agent": self.name,
                        "processing_mode": processing_mode,
                        "execution_state_preview": exec_preview,
                    },
                )
                refined_query = refinement_result.refined
            except Exception as e:
                logger.warning(
                    "[%s] FinalRefinementService failed; keeping original refined_query: %s",
                    self.name,
                    e,
                    exc_info=True,
                )

        # ------------------------------------------------------------------
        # 5) Store results in execution_state for downstream agents
        # ------------------------------------------------------------------
        if not hasattr(context, "execution_state") or not isinstance(context.execution_state, dict):
            context.execution_state = {}

        context.execution_state.setdefault("refiner", {})
        context.execution_state["refiner"].update(
            {
                "original_query": query,
                "refined_query": refined_query,
                "processing_mode": processing_mode,
                "cheap_confidence": cheap_conf,
                "entities": entities,
                "date_filters": date_filters,
                "flags": flags,
            }
        )
        context.execution_state["refined_query"] = refined_query

        if refinement_result is not None:
            context.execution_state["refiner"]["final_refinement"] = {
                "changed": refinement_result.changed,
                "error": refinement_result.error,
            }

        # 6) Build meta payload
        meta: Dict[str, Any] = {
            "processing_mode": processing_mode,
            "agent": self.name,
            "original_query": query,
            "cheap_confidence": cheap_conf,
            "skip_llm": skip_llm,
            "entities": entities,
            "date_filters": date_filters,
            "flags": flags,
        }
        try:
            meta["task_classification"] = context.get_task_classification()
            meta["cognitive_classification"] = context.get_cognitive_classification()
        except Exception:
            pass

        try:
            structured_outputs = context.execution_state.get("structured_outputs", {})
            if isinstance(structured_outputs, dict) and self.name in structured_outputs:
                meta["structured_output"] = structured_outputs[self.name]
        except Exception:
            pass

        if refinement_result is not None:
            meta["final_refinement"] = {
                "changed": refinement_result.changed,
                "error": refinement_result.error,
            }

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

    # ----------------------------------------------------------------------
    # Node metadata (for LangGraph / registry)
    # ----------------------------------------------------------------------
    def define_node_metadata(self) -> Dict[str, Any]:
        return {
            "node_type": NodeType.PROCESSOR,
            "dependencies": [],
            "description": "Transforms raw user queries into refined queries plus structured entities/date filters/flags.",
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
                    description="Updated context with refined query and structured details added",
                    type_hint="AgentContext",
                )
            ],
            "tags": ["refiner", "agent", "processor", "entry_point"],
        }
