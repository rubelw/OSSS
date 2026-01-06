from __future__ import annotations

from copy import deepcopy

from OSSS.ai.agents.base_agent import (
    BaseAgent,
    NodeType,
    NodeInputSchema,
    NodeOutputSchema,
)

import os
import re
import json
import logging
import asyncio
import importlib
from typing import Optional, Any, Dict, Tuple

import joblib  # 👈 for joblib-style models

from OSSS.ai.context import AgentContext
from OSSS.ai.llm.llm_interface import LLMInterface
from .prompts import REFINER_SYSTEM_PROMPT, DCG_CANONICALIZATION_BLOCK

# Structured output imports
from OSSS.ai.agents.models import RefinerOutput
from OSSS.ai.services.langchain_service import LangChainService

# Configuration system imports
from OSSS.ai.config.agent_configs import RefinerConfig
from OSSS.ai.workflows.prompt_composer import PromptComposer

# ✅ final refinement service
from OSSS.ai.services.final_refinement_service import (
    FinalRefinementService,
    FinalRefinementResult,
)

# ✅ NLP extraction service
from OSSS.ai.services.nlp_extraction_service import NLPExtractionService

logger = logging.getLogger(__name__)

# 👇 default on-disk model path (can be overridden by config or env)
DEFAULT_REFINER_MODEL_PATH = os.getenv(
    "OSSS_REFINER_MODEL_PATH",
    "/workspace/data_model/refiner/models/refiner_nn.joblib",
)

# ✅ deterministic CRUD prefix parser for "query consents", etc.
CRUD_PREFIX_RE = re.compile(
    r"^(query|read|select|create|insert|update|modify|delete|upsert)\s+(\S+)",
    re.IGNORECASE,
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

    # ----------------------------------------------------------------------
    # ✅ Joblib model loading (robust under uvicorn / __mp_main__)
    # ----------------------------------------------------------------------
    def _load_joblib_model(self, model_path: str) -> Any:
        """
        Robust joblib loader.

        Handles common uvicorn/__mp_main__ unpickle failure by:
        - importing a configured module that defines the pickled class
        - emitting a clear remediation message if the pickle references __main__/__mp_main__
        """
        # Optional module to import BEFORE joblib.load so pickled classes resolve.
        # You can set either config.joblib_model_module or env OSSS_REFINER_MODEL_MODULE.
        module_hint = getattr(self.config, "joblib_model_module", None) or os.getenv("OSSS_REFINER_MODEL_MODULE")

        if module_hint:
            try:
                importlib.import_module(module_hint)
                logger.info("[%s] Imported joblib model module hint: %s", self.name, module_hint)
            except Exception as e:
                logger.warning(
                    "[%s] Failed to import joblib model module hint '%s' (continuing): %s",
                    self.name,
                    module_hint,
                    e,
                )

        try:
            return joblib.load(model_path)
        except AttributeError as e:
            msg = str(e)

            # This is the exact class-resolution failure pattern you hit under uvicorn.
            if "__mp_main__" in msg or "__main__" in msg or "Can't get attribute" in msg:
                logger.warning(
                    "[%s] Joblib refiner model could not be unpickled under uvicorn. "
                    "This usually means the model was pickled with a class defined in __main__ "
                    "(or a non-importable module). "
                    "Fix: move the class to an importable module and re-save the joblib, "
                    "OR set OSSS_REFINER_MODEL_MODULE to that module so it is imported before loading. "
                    "Disabling joblib refiner for this run. Error=%s",
                    self.name,
                    msg,
                )
                return None

            logger.warning("[%s] Joblib refiner model load failed (AttributeError): %s", self.name, msg)
            return None
        except Exception as e:
            logger.warning("[%s] Joblib refiner model load failed; disabling: %s", self.name, e)
            return None

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

        # ✅ optional joblib-backed lightweight refiner
        self._joblib_model = None

        # 1) Prefer explicit config override if present
        cfg_path = getattr(self.config, "joblib_model_path", None)

        # 2) Fall back to default path (can also be overridden via OSSS_REFINER_MODEL_PATH)
        model_path = cfg_path or DEFAULT_REFINER_MODEL_PATH

        if model_path:
            if not os.path.exists(model_path):
                logger.warning("[%s] Joblib refiner model path does not exist: %s", self.name, model_path)
            else:
                loaded = self._load_joblib_model(model_path)
                self._joblib_model = loaded if loaded is not None else None
                if self._joblib_model is not None:
                    logger.info("[%s] Loaded joblib refiner model from %s", self.name, model_path)

        # ✅ NLP extraction service (best-effort, non-LLM)
        enable_nlp = getattr(self.config, "enable_nlp_extraction", True)
        self._nlp_service: Optional[NLPExtractionService] = NLPExtractionService(
            enabled=enable_nlp,
            model_name=getattr(self.config, "nlp_model_name", "en_core_web_sm"),
        )

        # ✅ Superset contract-mode friendly:
        #    Only enable final_refinement when config explicitly allows it.
        enable_final_refinement = bool(getattr(self.config, "enable_final_refinement", False))
        if enable_final_refinement:
            self._final_refinement_service: Optional[FinalRefinementService] = FinalRefinementService(
                style_hint="clear, concise, helpful for school staff and admins",
                enabled=True,
            )
        else:
            self._final_refinement_service = None

        logger.debug(f"[{self.name}] RefinerAgent initialized with config: {self.config}")

    # ----------------------------------------------------------------------
    # ✅ Fix 1 (Contract Superset Mode): prevent non-canonical "pattern" leakage
    # ----------------------------------------------------------------------
    def _sanitize_contract_fields(
        self,
        *,
        entities: Dict[str, Any],
        date_filters: Dict[str, Any],
        flags: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Fix 1: Pattern names are contracts and must be canonical only.

        The Refiner MUST NOT emit/propagate any graph/planning/pattern fields, because:
          - "superset" is not a pattern name
          - planning/routing happens elsewhere (orchestrator/planner)

        This protects the system from accidental LLM outputs like:
          flags.pattern="superset" / flags.graph_pattern="superset"
        """
        if not isinstance(entities, dict):
            entities = {}
        if not isinstance(date_filters, dict):
            date_filters = {}
        if not isinstance(flags, dict):
            flags = {}

        # Work on copies to avoid mutating dicts that might be shared
        entities = deepcopy(entities)
        date_filters = deepcopy(date_filters)
        flags = deepcopy(flags)

        # Strip any planning/graph/pattern fields if present (from LLM hallucinations or legacy clients)
        banned_flag_keys = {
            "pattern",
            "graph_pattern",
            "graph",
            "router_pattern",
            "resume_pattern",
            "planner_pattern",
            "compile_variant",  # planner/orchestrator concern, not refiner concern
            "agents_superset",  # planner/orchestrator concern, not refiner concern
            "superset",  # ambiguous; never a valid contract pattern name
        }
        for k in list(flags.keys()):
            if k in banned_flag_keys:
                flags.pop(k, None)

        # Also strip any nested variants if LLM shoved them under meta-ish buckets
        for bucket_key in ("routing", "planner", "orchestration", "graph_config", "compile"):
            v = flags.get(bucket_key)
            if isinstance(v, dict):
                for k in list(v.keys()):
                    if k in banned_flag_keys:
                        v.pop(k, None)
                if not v:
                    flags.pop(bucket_key, None)

        return entities, date_filters, flags

    # ----------------------------------------------------------------------
    # ✅ PR5: Stable refiner_output contract helpers
    # ----------------------------------------------------------------------
    def _build_refiner_output_markdown(self, refined_query: str, signals: Dict[str, Any]) -> str:
        """
        Optional human-readable summary for downstream prompts/logging.

        Keep it short. FinalAgent can include it as context if desired.
        """
        preview_keys = [
            "processing_mode",
            "skip_llm",
            "cheap_confidence",
            "is_db_command",
            "crud_verb",
            "db_target",
            "task_classification",
            "cognitive_classification",
        ]
        lines = ["### Refiner Output", "", f"**Refined query:** {refined_query}", "", "**Signals:**"]
        for k in preview_keys:
            if k in signals and signals[k] not in (None, "", {}, []):
                lines.append(f"- **{k}**: `{signals[k]}`")
        return "\n".join(lines).strip()

    def _write_refiner_output_contract(
        self,
        context: AgentContext,
        *,
        refined_query: str,
        processing_mode: str,
        skip_llm: bool,
        cheap_confidence: float,
        entities: Dict[str, Any],
        date_filters: Dict[str, Any],
        flags: Dict[str, Any],
        original_query: str,
    ) -> None:
        """
        ✅ PR5 contract:
          execution_state["refiner_output"] = {
            "refined_query": str,
            "analysis_signals": dict,
            "text_markdown": Optional[str],
          }
        """
        if not hasattr(context, "execution_state") or not isinstance(context.execution_state, dict):
            context.execution_state = {}

        # Fix 1 safety: ensure we never persist any non-contract planning/pattern fields
        entities, date_filters, flags = self._sanitize_contract_fields(
            entities=entities,
            date_filters=date_filters,
            flags=flags,
        )

        analysis_signals: Dict[str, Any] = {
            "processing_mode": processing_mode,
            "skip_llm": skip_llm,
            "cheap_confidence": cheap_confidence,
            "entities": entities,
            "date_filters": date_filters,
            "flags": flags,
            "is_db_command": self._looks_like_db_command(original_query),
        }

        # include parsed db target if we can (best-effort)
        try:
            parsed = self._parse_prefix_command(original_query)
            if parsed:
                analysis_signals["db_target"] = parsed[1]
        except Exception:
            pass

        # include classifier signals if present (best-effort)
        try:
            analysis_signals["task_classification"] = context.get_task_classification()
            analysis_signals["cognitive_classification"] = context.get_cognitive_classification()
        except Exception:
            pass

        # include inferred crud verb if we have it
        try:
            if isinstance(flags, dict):
                cv = flags.get("crud_verb")
                if isinstance(cv, str) and cv.strip():
                    analysis_signals["crud_verb"] = cv.strip().lower()
        except Exception:
            pass

        include_md = bool(getattr(self.config, "emit_refiner_output_markdown", True))
        text_markdown = (
            self._build_refiner_output_markdown(refined_query, analysis_signals) if include_md else None
        )

        context.execution_state["refiner_output"] = {
            "refined_query": refined_query,
            "analysis_signals": analysis_signals,
            "text_markdown": text_markdown,
        }

    # --- cheap / heuristic refiner helpers ---------------------------------

    def _looks_like_db_command(self, q: str) -> bool:
        """Very small heuristic: treat explicit CRUD-ish commands as DB/data operations."""
        if not q:
            return False

        ql = q.strip().lower()
        return ql.startswith(
            ("query ", "select ", "read ", "create ", "insert ", "update ", "modify ", "delete ", "upsert ")
        )

    def _is_simple_db_command(self, q: str) -> bool:
        """True for the common fast-path: `query <thing>` with minimal extra structure."""
        if not q:
            return False

        ql = q.strip().lower()
        return bool(re.match(r"^(query)\s+\S+(\s*)$", ql))

    def _parse_prefix_command(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Deterministically parse explicit commands like:
          "query consents" -> ("query", "consents")

        Returns (verb, target) or None.
        """
        if not text:
            return None
        m = CRUD_PREFIX_RE.match(text.strip())
        if not m:
            return None
        verb = m.group(1).lower()
        target = m.group(2).strip().strip(",.;:()[]{}")
        return verb, target

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
        lower = q.lower()
        if "dcg" in lower:
            q = q.replace("DCG", "Dallas Center-Grimes School District")
            q = q.replace("dcg", "Dallas Center-Grimes School District")

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
            result = self._joblib_model.predict([query])[0]

            if isinstance(result, dict):
                rq = result.get("refined_query") or result.get("text")
                conf = float(result.get("confidence", 0.0))
                if isinstance(rq, str) and rq.strip():
                    return rq.strip(), conf
                return None

            if isinstance(result, str) and result.strip():
                return result.strip(), 0.9

            return None
        except Exception as e:
            logger.warning("[%s] joblib refiner failed; ignoring and falling back: %s", self.name, e)
            return None

    def _cheap_refine(self, query: str) -> Tuple[str, float, bool]:
        """
        Run fast, non-LLM refinement and return:

        (refined_query, confidence, should_skip_llm)
        """
        if not query:
            return "", 0.0, False

        q = query.strip()
        original = q

        # 🚀 Fast-path: explicit simple DB command like "query consents"
        if self._is_simple_db_command(q):
            q_rules = self._apply_cheap_rules(q)
            return q_rules, 0.95, True

        q_rules = self._apply_cheap_rules(q)

        joblib_result = self._joblib_refine(q_rules)
        if joblib_result is not None:
            refined_joblib, conf = joblib_result

            max_len = getattr(self.config, "max_simple_length", 120)
            if conf >= 0.8 and len(q) <= max_len:
                return refined_joblib, conf, True

            return refined_joblib, conf, False

        if q_rules == original:
            if self._looks_like_db_command(q_rules) and len(q_rules) <= getattr(self.config, "max_simple_length", 120):
                return q_rules, 0.85, True
            return q_rules, 0.4, False

        if self._looks_like_db_command(q_rules) and len(q_rules) <= getattr(self.config, "max_simple_length", 120):
            return q_rules, 0.85, True

        return q_rules, 0.7, len(q) <= getattr(self.config, "max_simple_length", 120)

    # ----------------------------------------------------------------------
    # DCG injection + prompt plumbing
    # ----------------------------------------------------------------------
    def _inject_dcg_rule(self, system_prompt: str) -> str:
        if not isinstance(system_prompt, str):
            return system_prompt
        if (
            "Dallas Center-Grimes School District" in system_prompt
            or "ABSOLUTE CANONICALIZATION RULE" in system_prompt
        ):
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
        """User message content for the refiner call."""
        return (
            f"Original query:\n{query}\n\n"
            "Please refine this query and emit ONLY the JSON object described in the system instructions."
        )

    def update_config(self, config: RefinerConfig) -> None:
        self.config = config
        self._update_composed_prompt()
        logger.info(f"[{self.name}] Configuration updated: {config.refinement_level} refinement")

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

        processing_time_ms = (time.time() - start_time) * 1000
        if getattr(structured_result, "processing_time_ms", None) is None:
            structured_result = structured_result.model_copy(update={"processing_time_ms": processing_time_ms})

        # Persist structured result snapshot
        if not hasattr(context, "execution_state") or not isinstance(context.execution_state, dict):
            context.execution_state = {}

        context.execution_state.setdefault("structured_outputs", {})
        context.execution_state["structured_outputs"][self.name] = structured_result.model_dump()

        if not hasattr(context, "execution_metadata") or not isinstance(context.execution_metadata, dict):
            context.execution_metadata = {}
        context.execution_metadata.setdefault("agent_outputs", {})
        context.execution_metadata["agent_outputs"][self.name] = structured_result.model_dump()

        base = structured_result.model_dump()
        refined_query = (base.get("refined_query") or query).strip() or query
        entities = base.get("entities") or {}
        date_filters = base.get("date_filters") or {}
        flags = base.get("flags") or {}

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

    # ----------------------------------------------------------------------
    # Helpers: normalize LLM response -> canonical schema
    # ----------------------------------------------------------------------
    def _normalize_refiner_obj(self, obj: Any, fallback_query: str) -> Dict[str, Any]:
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

    def _extract_refiner_obj_from_llm_response(self, resp: Any, fallback_query: str) -> Dict[str, Any]:
        # ✅ 0) Preferred: OSSS LLMResponse-style wrapper
        try:
            resp_text = getattr(resp, "text", None)
            if isinstance(resp_text, str) and resp_text.strip():
                # resp.text is expected to be the model content
                return self._normalize_refiner_obj(json.loads(resp_text), fallback_query=fallback_query)
        except Exception:
            # If it's not valid JSON, we'll fall through and handle it as text later
            pass

        # ✅ 0b) If there's a raw OpenAI ChatCompletion under resp.raw, use that
        try:
            raw = getattr(resp, "raw", None)
            if raw is not None:
                return self._extract_refiner_obj_from_llm_response(raw, fallback_query=fallback_query)
        except Exception:
            pass

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
            content = None

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

        # Try parse as JSON
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return self._normalize_refiner_obj(parsed, fallback_query=fallback_query)
        except Exception:
            pass

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

        timeout_s = getattr(getattr(self.config, "execution_config", None), "timeout_seconds", None) or 60
        logger.info(
            "[%s] LLM request start",
            self.name,
            extra={"event": "refiner_llm_request_start", "timeout_seconds": timeout_s},
        )
        try:
            resp = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.error(
                "[%s] LLM request timed out after %ss (falling back to cheap result)",
                self.name,
                timeout_s,
            )
            return {"refined_query": query, "entities": {}, "date_filters": {}, "flags": {}}
        finally:
            logger.info("[%s] LLM request end", self.name, extra={"event": "refiner_llm_request_end"})

        input_tokens = getattr(resp, "input_tokens", 0) or 0
        output_tokens = getattr(resp, "output_tokens", 0) or 0
        total_tokens = getattr(resp, "tokens_used", 0) or 0

        context.add_agent_token_usage(
            agent_name=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        return self._extract_refiner_obj_from_llm_response(resp, fallback_query=query)

    # ----------------------------------------------------------------------
    # Query extraction from context
    # ----------------------------------------------------------------------
    def _extract_query_text(self, context: AgentContext) -> str:
        raw: Any = None

        try:
            raw = context.get_user_question()
        except Exception as e:
            logger.debug(f"[{self.name}] get_user_question() failed: {e}")

        if not raw:
            raw = getattr(context, "query", None)

        if isinstance(raw, str):
            return raw.strip()

        if isinstance(raw, dict):
            for key in ("query", "text", "content", "message"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            try:
                return json.dumps(raw, ensure_ascii=False).strip()
            except Exception:
                return ""

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
        query = self._extract_query_text(context)
        system_prompt = self._get_system_prompt()

        use_structured = bool(getattr(self.config, "use_structured_output", False) and self.structured_service)
        processing_mode = "traditional"

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

        # ✅ BEST PRACTICE: for explicit DB commands, cheap-only is sufficient.
        #    Let routing/data_query handle the wizard and downstream steps.
        #    Allow opting back into forced LLM via config/env if desired.
        if skip_llm and self._looks_like_db_command(query):
            force_llm_for_db = bool(getattr(self.config, "force_llm_for_db_commands", False)) or (
                os.getenv("OSSS_FORCE_LLM_FOR_DB_COMMANDS", "").strip().lower() in ("1", "true", "yes", "y")
            )
            if force_llm_for_db:
                logger.info(
                    "[%s] force_llm_for_db_commands enabled; will run LLM for DB command",
                    self.name,
                    extra={"event": "refiner_force_llm_for_db_command", "query_preview": query[:200]},
                )
                skip_llm = False
            else:
                logger.info(
                    "[%s] Keeping skip_llm=True for DB command (best practice: deterministic refiner)",
                    self.name,
                    extra={"event": "refiner_skip_llm_kept_for_db_command", "query_preview": query[:200]},
                )

        refined_query = cheap_refined or query

        entities: Dict[str, Any] = {}
        date_filters: Dict[str, Any] = {}
        flags: Dict[str, Any] = {}

        # ------------------------------------------------------------------
        # 2) Optional LLM-based refinement
        # ------------------------------------------------------------------
        if skip_llm:
            processing_mode = "lightweight"

            # ✅ For explicit DB commands, populate minimal deterministic entities/flags
            #    so downstream wizard/table resolution doesn't depend on classifier confidence.
            parsed = self._parse_prefix_command(refined_query)
            if parsed:
                verb, target = parsed
                flags = {
                    "is_database_query": True,
                    "is_crud_operation": True,
                    "crud_verb": verb,
                    "refiner_mode": "cheap_only",
                }
                if target:
                    # These are intentionally redundant; downstream code can read whichever it prefers.
                    entities = {
                        "collection": target,
                        "table_name": target,
                        "topic": target,
                    }
                    # Some downstream agents may look under flags for routing hints.
                    flags["db_target"] = target
            elif self._looks_like_db_command(refined_query):
                tokens = refined_query.split()
                flags = {
                    "is_database_query": True,
                    "is_crud_operation": True,
                    "crud_verb": tokens[0].lower() if tokens else "query",
                    "refiner_mode": "cheap_only",
                }
        else:
            if use_structured:
                try:
                    processing_mode = "structured"
                    refiner_obj = await self._run_structured(refined_query, system_prompt, context)
                except Exception as e:
                    logger.warning("[%s] Structured mode failed, falling back to traditional: %s", self.name, e)
                    processing_mode = "traditional"
                    refiner_obj = await self._run_traditional(refined_query, system_prompt, context)
            else:
                processing_mode = "traditional"
                refiner_obj = await self._run_traditional(refined_query, system_prompt, context)

            refined_query = refiner_obj.get("refined_query", refined_query)
            entities = refiner_obj.get("entities", {}) or {}
            date_filters = refiner_obj.get("date_filters", {}) or {}
            flags = refiner_obj.get("flags", {}) or {}

        # ------------------------------------------------------------------
        # 3) Optional NLP extraction (non-LLM)
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
                logger.warning("[%s] NLPExtractionService.extract failed; continuing without NLP: %s", self.name, e)

        # ✅ Fix 1: sanitize any leaked pattern/planning fields from LLM/NLP merges
        entities, date_filters, flags = self._sanitize_contract_fields(
            entities=entities,
            date_filters=date_filters,
            flags=flags,
        )

        # ------------------------------------------------------------------
        # 4) Optional final refinement service pass (LLM-based)
        #    ✅ contract-mode friendly: only runs if config.enable_final_refinement True
        # ------------------------------------------------------------------
        refinement_result: Optional[FinalRefinementResult] = None
        service = getattr(self, "_final_refinement_service", None)

        if service is not None and not skip_llm and bool(getattr(self.config, "enable_final_refinement", False)):
            try:
                exec_preview: Any = getattr(context, "execution_state", {})
                if isinstance(exec_preview, dict):
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

        # Fix 1 safety (again, before persistence): make sure contract is clean
        entities, date_filters, flags = self._sanitize_contract_fields(
            entities=entities,
            date_filters=date_filters,
            flags=flags,
        )

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

        # ✅ PR5: stable refiner_output contract (ALWAYS written)
        self._write_refiner_output_contract(
            context,
            refined_query=refined_query,
            processing_mode=processing_mode,
            skip_llm=skip_llm,
            cheap_confidence=cheap_conf,
            entities=entities,
            date_filters=date_filters,
            flags=flags,
            original_query=query,
        )

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
