"""
Final agent (RAG + formatted final text).

Compatibility:
- Must be callable via BaseAgent.run_with_retry(ctx)
- Therefore FinalAgent.run signature MUST be: run(self, ctx: AgentContext) -> AgentContext
- Must write final text into ctx under key "final"
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

from OSSS.ai.llm.factory import LLMFactory  # ✅ use factory so request-level use_rag/top_k can apply
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.utils.llm_text import coerce_llm_text

# Configuration + prompt composer imports (follow SynthesisAgent pattern)
from OSSS.ai.config.agent_configs import FinalConfig
from OSSS.ai.workflows.prompt_composer import ComposedPrompt, PromptComposer

# Final-specific prompts (system + user template)
from OSSS.ai.agents.final.prompts import FINAL_SYSTEM_PROMPT, build_final_prompt

# Structured final state (for LangGraph OSSSState.final)
from OSSS.ai.orchestration.state_schemas import FinalState

logger = get_logger(__name__)

_REFINE_PREFIXES: Tuple[str, ...] = (
    "refined query:",
    "**refined query:**",
    "**refined query**",
    "refined query",
    "here's a refined version",
    "here is a refined version",
    "here's a refined version of the original query",
    "here is a refined version of the original query",
    "refined version of the query",
    "to accurately answer your original query",
)

# Role titles where we absolutely do NOT want to hallucinate identities
_ROLE_IDENTITY_KEYWORDS: Tuple[str, ...] = (
    "superintendent",
    "principal",
    "mayor",
    "director",
    "president",
    "ceo",
    "head of school",
    "chancellor",
    "dean",
)


class FinalAgent(BaseAgent):
    """
    FinalAgent: produces the end-user answer using RAG snippets + prior agent context.

    - Respects role-identity constraints (no hallucinating real-world office holders).
    - Integrates with execution_config via LLMFactory (so use_rag/top_k flow through).
    - Uses FinalConfig + PromptComposer to align with other agents (Historian/Synthesis).
    - NOTE: This implementation performs exactly one LLM call per run (except the
      prompt-delivery and data_query short-circuit paths, which can bypass LLM entirely).

    ✅ HARDENING (PR5.1+):
      - If upstream (e.g., data_query) already wrote a user-facing prompt into exec_state["final"]
        as a STRING, FinalAgent must DELIVER it and must NOT overwrite exec_state["final"] with a dict.
      - exec_state["final"] is always the user-visible STRING.
      - Structured FinalState is stored in exec_state["structured_outputs"]["final"].
    """

    write_output_alias: bool = False

    def __init__(
        self,
        llm: Optional[Union[LLMInterface, str]] = "default",
        config: Optional[FinalConfig] = None,
        name: str = "final",
        **kwargs: Any,
    ) -> None:
        self.config: FinalConfig = config if config is not None else FinalConfig()

        super().__init__(
            name=name,
            timeout_seconds=self.config.execution_config.timeout_seconds,
            **kwargs,
        )

        self._prompt_composer = PromptComposer()
        self._composed_prompt: Optional[ComposedPrompt] = None

        if llm == "default":
            self.llm: Optional[LLMInterface] = None
        else:
            if llm is None:
                self.llm = None
            elif hasattr(llm, "generate") or hasattr(llm, "ainvoke"):
                self.llm = llm  # type: ignore[assignment]
            else:
                self.llm = None

        self._update_composed_prompt()

    # -----------------------
    # safe ctx access
    # -----------------------

    def _ctx_get(self, ctx: AgentContext, key: str, default: Any = None) -> Any:
        """
        AgentContext isn't guaranteed to be dict-like. Support:
        - ctx.get(key) if it exists
        - getattr(ctx, key)
        - ctx[key] if it implements __getitem__
        """
        try:
            getter = getattr(ctx, "get", None)
            if callable(getter):
                return getter(key, default)
        except Exception:
            pass

        try:
            if hasattr(ctx, key):
                return getattr(ctx, key)
        except Exception:
            pass

        try:
            return ctx[key]  # type: ignore[index]
        except Exception:
            return default

    def _set_ctx_final_text(self, ctx: AgentContext, text: str) -> None:
        """
        Hard guarantee: write final text into ctx under key "final" (string).
        """
        try:
            ctx.set("final", text)
        except Exception:
            pass
        try:
            setattr(ctx, "final", text)
        except Exception:
            pass

    # -----------------------
    # prompt-delivery hardening
    # -----------------------

    def _get_pending_action_prompt(self, exec_state: Dict[str, Any]) -> str:
        pa = exec_state.get("pending_action")
        if not isinstance(pa, dict):
            return ""
        for k in ("display_prompt", "user_message", "prompt", "question"):
            v = pa.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _should_bypass_llm_for_prompt_delivery(self, exec_state: Dict[str, Any]) -> bool:
        # canonical wizard prompt marker
        if bool(exec_state.get("wizard_prompted_this_turn")):
            return True

        # awaiting protocol reply
        pa = exec_state.get("pending_action")
        if isinstance(pa, dict) and pa.get("awaiting") is True:
            return True

        # upstream explicitly suppresses history and already has a final string
        if bool(exec_state.get("suppress_history")) and isinstance(exec_state.get("final"), str):
            return True

        return False

    # -----------------------
    # heuristics
    # -----------------------

    def _looks_like_refiner_text(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        t = text.strip().lower()
        if not t:
            return False

        if t.startswith("[unchanged]"):
            return True

        if t.startswith(_REFINE_PREFIXES):
            return True

        if "refined query" in t and (
            "contextual information" in t or "revised query" in t or "original query" in t
        ):
            return True

        if t.count("\n") >= 3 and ("###" in t or "**" in t) and "refin" in t:
            return True

        if "refined" in t and ("====" in t or "----" in t):
            return True

        if "canonicalization rule" in t and "dcg" in t:
            return True

        return False

    def _looks_like_metadata_dump(self, text: str) -> bool:
        """
        Detect the exact kind of blob you're seeing in logs:
        "This is a JSON object containing metadata about a conversation..."
        """
        if not isinstance(text, str):
            return False
        t = text.strip()
        if not t:
            return False

        low = t.lower()

        if "this is a json object" in low and "metadata" in low and "conversation" in low:
            return True
        if "classifier profile" in low and "conversation id" in low:
            return True
        if "agent outputs" in low and "orchestrator" in low:
            return True

        braces = t.count("{") + t.count("}")
        colons = t.count(":")
        qmarks = t.count("?")
        if len(t) > 400 and (braces > 10 or colons > 30) and qmarks == 0:
            return True

        if len(t) > 400 and (t.count("\\n") > 8 or t.count("\\\\") > 8):
            return True

        return False

    def _looks_like_user_question(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        s = text.strip()
        if not s:
            return False
        if self._looks_like_metadata_dump(s):
            return False
        if len(s) > 240:
            return False
        return True

    def _normalize_refiner_to_question(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        s = text.strip()
        low = s.lower()
        if low.startswith("[unchanged]"):
            return s[len("[unchanged]") :].strip()
        if low.startswith("refined query:"):
            return s[len("refined query:") :].strip()
        return s

    def _pick_first_str(self, *vals: Any) -> str:
        for v in vals:
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _pick_longest_str(self, *vals: Any) -> str:
        best = ""
        for v in vals:
            if isinstance(v, str):
                s = v.strip()
                if len(s) > len(best):
                    best = s
        return best

    # -----------------------
    # ✅ stable context formatting
    # -----------------------

    def _format_refiner_output_for_prompt(self, refiner_out: Any) -> str:
        if refiner_out is None:
            return ""
        if isinstance(refiner_out, str):
            return refiner_out.strip()
        if isinstance(refiner_out, (dict, list, tuple)):
            try:
                return json.dumps(refiner_out, indent=2, sort_keys=True, default=str).strip()
            except Exception:
                return str(refiner_out).strip()
        return str(refiner_out).strip()

    def _truncate_block(self, text: str, limit: int = 4000) -> str:
        if not isinstance(text, str):
            return ""
        s = text.strip()
        if len(s) <= limit:
            return s
        head = s[:limit].rstrip()
        return head + "\n... [truncated]\n"

    def _discover_refiner_output_struct(self, ctx: AgentContext, exec_state: Dict[str, Any]) -> Any:
        """
        PR5: ensure we always have *some* refiner_output artifact available for prompt inclusion.
        Priority:
          1) exec_state["refiner_output"]
          2) ctx.get_last_output("refiner")
          3) ctx/refiner_output or ctx/refiner
          4) agent_outputs["refiner"]
        """
        if isinstance(exec_state, dict) and "refiner_output" in exec_state:
            return exec_state.get("refiner_output")

        get_last = getattr(ctx, "get_last_output", None)
        if callable(get_last):
            try:
                v = get_last("refiner")
                if v is not None:
                    return v
            except Exception:
                pass

        v2 = self._ctx_get(ctx, "refiner_output")
        if v2 is not None:
            return v2

        v3 = self._ctx_get(ctx, "refiner")
        if v3 is not None:
            return v3

        agent_outputs = getattr(ctx, "agent_outputs", None) or {}
        v4 = agent_outputs.get("refiner")
        if v4 is not None:
            return v4

        return None

    # -----------------------
    # role-identity question detection
    # -----------------------

    def _is_role_identity_question(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        t = text.strip().lower()
        if not t:
            return False

        has_role_keyword = any(kw in t for kw in _ROLE_IDENTITY_KEYWORDS)
        if not has_role_keyword:
            return False

        if "who is" in t or "who's" in t or t.startswith("who "):
            return True

        if t.startswith("is ") and any(f" the {kw}" in t for kw in _ROLE_IDENTITY_KEYWORDS):
            return True

        return False

    # -----------------------
    # trace/log discovery helpers (unchanged)
    # -----------------------

    def _iter_dictish_records(self, obj: Any) -> Iterable[Dict[str, Any]]:
        if isinstance(obj, dict):
            if any(k in obj for k in ("input", "output", "agent", "agent_name", "name")):
                yield obj
            for v in obj.values():
                if isinstance(v, (dict, list, tuple)):
                    yield from self._iter_dictish_records(v)
            return

        if isinstance(obj, (list, tuple)):
            for x in obj:
                if isinstance(x, (dict, list, tuple)):
                    yield from self._iter_dictish_records(x)

    def _iter_trace_candidates(self, ctx: AgentContext) -> List[Any]:
        candidates: List[Any] = []
        try:
            for k, v in vars(ctx).items():
                lk = k.lower()
                if any(tok in lk for tok in ("trace", "log", "event", "history")):
                    candidates.append(v)
        except Exception:
            pass

        exec_state = getattr(ctx, "execution_state", None)
        if isinstance(exec_state, dict):
            for k, v in exec_state.items():
                lk = str(k).lower()
                if any(tok in lk for tok in ("trace", "log", "event", "history")):
                    candidates.append(v)

        for name in ("traces", "trace_log", "agent_traces", "events", "logs"):
            candidates.append(getattr(ctx, name, None))
            if isinstance(exec_state, dict):
                candidates.append(exec_state.get(name))

        return candidates

    def _iter_trace_dicts(self, ctx: AgentContext) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for c in self._iter_trace_candidates(ctx):
            if c is None:
                continue
            out.extend(list(self._iter_dictish_records(c)))

        expanded: List[Dict[str, Any]] = []
        for rec in out:
            expanded.append(rec)
            for key in ("items", "records", "entries", "data"):
                v = rec.get(key)
                if isinstance(v, list):
                    expanded.extend([x for x in v if isinstance(x, dict)])
        return expanded

    # -----------------------
    # original query / refiner recovery (mostly unchanged)
    # -----------------------

    def _get_classifier_original_text(self, exec_state: Dict[str, Any]) -> str:
        prof = exec_state.get("classifier_profile") or exec_state.get("classifier_result") or {}
        if isinstance(prof, dict):
            for k in ("original_text", "normalized_text"):
                v = prof.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        cls = exec_state.get("classifier") or {}
        if isinstance(cls, dict):
            v = cls.get("original_text")
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _extract_refined_question_from_refiner(self, refiner_text: str) -> str:
        if not isinstance(refiner_text, str) or not refiner_text.strip():
            return ""

        lines = [ln.strip() for ln in refiner_text.splitlines() if ln.strip()]
        if not lines:
            return ""

        for ln in lines:
            low = ln.lower()
            if low.startswith("**improved query**") or low.startswith("improved query:"):
                if ":" in ln:
                    return ln.split(":", 1)[1].strip()

        for ln in lines:
            low = ln.lower()
            if low.startswith("refined query:"):
                return ln.split(":", 1)[1].strip()

        question_candidates = [ln for ln in lines if "?" in ln]
        if question_candidates:
            return question_candidates[-1].strip()

        return ""

    def _extract_best_refiner_text(self, ctx: AgentContext) -> str:
        exec_state = getattr(ctx, "execution_state", None)
        candidates: List[str] = []

        if isinstance(exec_state, dict):
            v = exec_state.get("refiner_full_text")
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())

        if isinstance(exec_state, dict):
            for key in ("agent_outputs", "outputs"):
                ao = exec_state.get(key)
                if isinstance(ao, dict):
                    v = ao.get("refiner")
                    if isinstance(v, str) and v.strip():
                        candidates.append(v.strip())

        get_output = getattr(ctx, "get_agent_output", None)
        if callable(get_output):
            try:
                v = get_output("refiner")
                if isinstance(v, str) and v.strip():
                    candidates.append(v.strip())
            except Exception:
                pass

        for container_name in ("traces", "trace_log"):
            traces = getattr(ctx, container_name, None)
            if not isinstance(traces, list):
                continue
            for tr in reversed(traces):
                if not isinstance(tr, dict):
                    continue
                outv = tr.get("output")
                if isinstance(outv, str) and outv.strip():
                    candidates.append(outv.strip())

        best = self._pick_longest_str(*candidates)

        if best and self._looks_like_refiner_text(best) and len(best) < 120 and len(best.splitlines()) <= 2:
            return ""

        return best

    # -----------------------
    # ✅ execution_config discovery (unchanged)
    # -----------------------

    def _get_execution_config(self, ctx: AgentContext) -> Dict[str, Any]:
        def _unwrap(v: Any) -> Dict[str, Any]:
            if not isinstance(v, dict):
                return {}
            nested = v.get("execution_config")
            if isinstance(nested, dict) and nested:
                return nested
            return v

        state = getattr(ctx, "execution_state", None)
        if isinstance(state, dict):
            cfg = state.get("config")
            if isinstance(cfg, dict):
                return _unwrap(cfg)

            v = state.get("execution_config")
            if isinstance(v, dict):
                return _unwrap(v)

            for key in ("raw_request_config", "raw_execution_config", "request_config"):
                vv = state.get(key)
                if isinstance(vv, dict):
                    return _unwrap(vv)

        v2 = getattr(ctx, "execution_config", None)
        if isinstance(v2, dict):
            return _unwrap(v2)

        return {}

    # -----------------------
    # prompt helpers
    # -----------------------

    def _update_composed_prompt(self) -> None:
        try:
            self._composed_prompt = self._prompt_composer.compose_final_prompt(self.config)
            logger.debug(f"[{self.name}] Prompt composed for FinalAgent with config.")
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to compose FinalAgent prompt, using default: {e}")
            self._composed_prompt = None

    def _get_system_prompt(self) -> str:
        if self._composed_prompt and self._prompt_composer.validate_composition(self._composed_prompt):
            return self._composed_prompt.system_prompt
        logger.debug(f"[{self.name}] Using default FinalAgent system prompt (fallback)")
        return FINAL_SYSTEM_PROMPT

    def _compose_prompt(self, ctx: AgentContext) -> tuple[str, str]:
        """
        Build system + user prompts for the FinalAgent.
        Ensures the raw/original user question survives wizard follow-ups.

        PR5:
          - Always include refiner_output (JSON or readable representation) in the composed prompt.
          - Include a data_query_note line if present.
        """
        exec_state = getattr(ctx, "execution_state", {}) or {}
        agent_outputs = getattr(ctx, "agent_outputs", None) or {}

        classifier_original = self._get_classifier_original_text(exec_state) if isinstance(exec_state, dict) else ""

        # ✅ PR5: stable refiner_output artifact for prompt inclusion (always present as a section)
        refiner_out_struct = self._discover_refiner_output_struct(ctx, exec_state if isinstance(exec_state, dict) else {})
        if isinstance(exec_state, dict) and exec_state.get("refiner_output") is None and refiner_out_struct is not None:
            exec_state["refiner_output"] = refiner_out_struct

        refiner_out_text = self._truncate_block(self._format_refiner_output_for_prompt(refiner_out_struct), limit=4000)

        data_query_note = ""
        if isinstance(exec_state, dict):
            v = exec_state.get("data_query_note")
            if isinstance(v, str) and v.strip():
                data_query_note = v.strip()

        # --- refiner text (best-effort) ---------------------------------------
        refiner_text = (
            self._ctx_get(ctx, "refiner")
            or self._ctx_get(ctx, "refiner_output")
            or (exec_state or {}).get("refiner_snippet")
            or (exec_state or {}).get("refiner_full_text")
            or (exec_state or {}).get("refiner")
            or (exec_state or {}).get("refiner_output")
            or agent_outputs.get("refiner")
        )

        if isinstance(refiner_text, dict):
            refiner_text = (
                refiner_text.get("text_markdown")
                or refiner_text.get("text")
                or refiner_text.get("content")
                or ""
            )

        refiner_text = refiner_text if isinstance(refiner_text, str) else ""
        refiner_text = (refiner_text or "").strip()

        # --- original user question ------------------------------------------
        original_question = self._pick_first_str(
            classifier_original,
            exec_state.get("wizard_original_query") if isinstance(exec_state, dict) else None,
            exec_state.get("wizard_reject_original_query") if isinstance(exec_state, dict) else None,
            exec_state.get("user_question") if isinstance(exec_state, dict) else None,
            exec_state.get("original_query") if isinstance(exec_state, dict) else None,
            exec_state.get("question") if isinstance(exec_state, dict) else None,
            exec_state.get("query") if isinstance(exec_state, dict) else None,
            getattr(ctx, "query", None),
        ).strip()

        # --- refined question selection --------------------------------------
        refined_question = ""

        if refiner_text:
            if self._looks_like_refiner_text(refiner_text):
                refined_question = (
                    self._extract_refined_question_from_refiner(refiner_text)
                    or self._normalize_refiner_to_question(refiner_text)
                )
            else:
                if not self._looks_like_metadata_dump(refiner_text):
                    refined_question = refiner_text

        refined_question = (refined_question or "").strip() or original_question

        # HARD RULE: if original starts with "query ", it always wins
        if original_question and original_question.lower().startswith("query "):
            refined_question = original_question

        # Safety: if original looks like a real short question, don't let long/dumpy override it
        if self._looks_like_user_question(original_question):
            if self._looks_like_metadata_dump(refined_question) or len(refined_question) > 240:
                refined_question = original_question

        if not refined_question:
            refined_question = original_question or "[missing user question]"

        # --- RAG snippet ------------------------------------------------------
        rag_snippet = ""
        if isinstance(exec_state, dict):
            rag_snippet = (exec_state.get("rag_snippet") or exec_state.get("rag_context") or "").strip()
        rag_present = bool(rag_snippet)

        # --- data_query markdown (if present) ---------------------------------
        dq_output = agent_outputs.get("data_query")
        data_query_markdown = ""
        if isinstance(dq_output, dict):
            data_query_markdown = (
                dq_output.get("table_markdown")
                or dq_output.get("markdown")
                or dq_output.get("content")
                or ""
            )
        elif isinstance(dq_output, str):
            data_query_markdown = dq_output
        data_query_markdown = (data_query_markdown or "").strip()

        rag_metadata = ""
        if isinstance(exec_state, dict):
            rag_metadata = (exec_state.get("rag_metadata") or exec_state.get("rag_meta") or "")

        data_query_metadata = ""
        if isinstance(dq_output, dict):
            data_query_metadata = dq_output.get("metadata") or dq_output.get("meta") or dq_output.get("info") or ""

        user_prompt = build_final_prompt(
            user_question=refined_question,
            refiner_text=refiner_text,
            rag_present=rag_present,
            rag_section=rag_snippet,
            original_user_question=original_question,
            data_query_markdown=data_query_markdown,
            config=self.config,
            rag_metadata=rag_metadata or None,
            data_query_metadata=data_query_metadata or None,
        )

        # ✅ PR5: append stable context blocks (ALWAYS include refiner_output section)
        extra_parts: List[str] = []
        if data_query_note:
            extra_parts.append(f"[Data query note] {data_query_note}")

        extra_parts.append("Refiner output (state.refiner_output):")
        extra_parts.append(refiner_out_text if refiner_out_text else "(none)")

        user_prompt = user_prompt.rstrip() + "\n\n---\n" + "\n".join(extra_parts).rstrip() + "\n"

        system_prompt = self._get_system_prompt()
        return system_prompt, user_prompt

    # -----------------------
    # bookkeeping (unchanged)
    # -----------------------

    def _get_execution_state(self, ctx: AgentContext) -> Dict[str, Any]:
        state = getattr(ctx, "execution_state", None)
        if not isinstance(state, dict):
            state = {}
            setattr(ctx, "execution_state", state)
        return state

    def _mark_started(self, ctx: AgentContext) -> None:
        state = self._get_execution_state(ctx)
        status = state.setdefault("agent_execution_status", {})
        rec = status.setdefault(self.name, {})
        rec.setdefault("started_at", datetime.now(timezone.utc).isoformat())
        rec.setdefault("completed_at", None)
        rec.setdefault("error", None)

    def _mark_completed(self, ctx: AgentContext) -> None:
        state = self._get_execution_state(ctx)
        status = state.setdefault("agent_execution_status", {})
        rec = status.setdefault(self.name, {})
        rec["completed_at"] = datetime.now(timezone.utc).isoformat()
        rec.setdefault("error", None)

    def _mark_failed(self, ctx: AgentContext, error: str) -> None:
        state = self._get_execution_state(ctx)
        status = state.setdefault("agent_execution_status", {})
        rec = status.setdefault(self.name, {})
        rec.setdefault("started_at", datetime.now(timezone.utc).isoformat())
        rec["completed_at"] = datetime.now(timezone.utc).isoformat()
        rec["error"] = error

    # -----------------------
    # ✅ LLM resolution via factory
    # -----------------------

    def _resolve_llm(self, ctx: AgentContext) -> LLMInterface:
        if self.llm is not None:
            return self.llm
        execution_config = self._get_execution_config(ctx)
        return LLMFactory.create(agent_name="final", execution_config=execution_config)

    def update_config(self, config: FinalConfig) -> None:
        self.config = config
        self._update_composed_prompt()
        logger.info(f"[{self.name}] Configuration updated for FinalAgent")

    # -----------------------
    # helpers to build structured FinalState
    # -----------------------

    def _build_sources_used(self, ctx: AgentContext, exec_state: Dict[str, Any]) -> List[str]:
        sources: List[str] = []
        agent_outputs = getattr(ctx, "agent_outputs", None) or {}

        for name in ("refiner", "historian", "critic", "data_query"):
            if name in agent_outputs:
                sources.append(name)

        rag_ctx = exec_state.get("rag_context")
        rag_enabled = bool(exec_state.get("rag_enabled")) and isinstance(rag_ctx, str) and rag_ctx.strip()
        if rag_enabled:
            sources.append("rag")

        seen = set()
        out: List[str] = []
        for s in sources:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def _store_structured_final(
        self,
        ctx: AgentContext,
        text: str,
        *,
        exec_state: Optional[Dict[str, Any]] = None,
        tone: Optional[str] = None,
        target_audience: Optional[str] = None,
    ) -> None:
        """
        ✅ HARDENING:
          - exec_state["final"] remains the user-visible STRING (always).
          - structured final goes to exec_state["structured_outputs"]["final"].
        """
        if exec_state is None:
            exec_state = self._get_execution_state(ctx)

        rag_ctx = exec_state.get("rag_context")
        rag_enabled = bool(exec_state.get("rag_enabled")) and isinstance(rag_ctx, str) and rag_ctx.strip()
        rag_snippet = exec_state.get("rag_snippet")
        if isinstance(rag_snippet, str):
            rag_snippet = rag_snippet.strip() or None
        else:
            rag_snippet = None

        sources_used = self._build_sources_used(ctx, exec_state)

        final_struct: FinalState = {
            "final_answer": text,
            "used_rag": bool(rag_enabled),
            "rag_excerpt": rag_snippet,
            "sources_used": sources_used,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if tone is not None:
            final_struct["tone"] = tone
        if target_audience is not None:
            final_struct["target_audience"] = target_audience

        # ✅ user-visible final stays a string
        exec_state["final"] = text

        structured = exec_state.get("structured_outputs")
        if not isinstance(structured, dict):
            structured = {}
            exec_state["structured_outputs"] = structured
        structured["final"] = final_struct

    def _strip_metadata_block(self, text: str) -> str:
        if not isinstance(text, str):
            return text
        marker = "Optional extra context (metadata, not user-visible):"
        lowered = text.lower()
        idx = lowered.find(marker.lower())
        if idx != -1:
            return text[:idx].rstrip()
        return text

    # -----------------------
    # main entrypoint
    # -----------------------

    async def run(self, ctx: AgentContext) -> AgentContext:
        self._mark_started(ctx)
        try:
            exec_state = self._get_execution_state(ctx)

            # ✅ Optional hardening: deliver wizard/protocol prompts without an LLM call
            if self._should_bypass_llm_for_prompt_delivery(exec_state):
                prompt_text = ""
                v = exec_state.get("final")
                if isinstance(v, str) and v.strip():
                    prompt_text = v.strip()
                if not prompt_text:
                    prompt_text = self._get_pending_action_prompt(exec_state)

                if prompt_text:
                    self._set_ctx_final_text(ctx, prompt_text)

                    ctx.add_agent_output(
                        agent_name=self.name,
                        logical_name="final",
                        content=prompt_text,
                        role="assistant",
                        action="answer",
                        intent="informational",
                        meta={"agent": self.name, "bypass_llm": True, "reason": "prompt_delivery"},
                    )

                    self._store_structured_final(
                        ctx,
                        prompt_text,
                        exec_state=exec_state,
                        tone="neutral",
                        target_audience=exec_state.get("target_audience") or getattr(ctx, "target_audience", None),
                    )

                    approx_tokens = len(prompt_text.split())
                    ctx.add_agent_token_usage(
                        agent_name=self.name,
                        input_tokens=0,
                        output_tokens=approx_tokens,
                        total_tokens=approx_tokens,
                    )

                    self._mark_completed(ctx)
                    return ctx

            # Prefer classifier original text for "query ..." detection
            classifier_original = self._get_classifier_original_text(exec_state)
            original_q = (
                classifier_original
                or exec_state.get("wizard_original_query")
                or exec_state.get("wizard_reject_original_query")
                or exec_state.get("user_question")
                or exec_state.get("original_query")
                or getattr(ctx, "query", "")
                or ""
            ).strip()

            # Resolve role-identity safety using the real question
            role_identity_q = self._is_role_identity_question(original_q)

            # Structured data-query short-circuit (only when there is a real table result)
            if original_q.lower().startswith("query "):
                agent_outputs = getattr(ctx, "agent_outputs", None) or {}
                dq_output = agent_outputs.get("data_query")

                data_query_markdown = ""
                if isinstance(dq_output, dict):
                    data_query_markdown = (
                        dq_output.get("table_markdown")
                        or dq_output.get("markdown")
                        or dq_output.get("content")
                        or ""
                    )
                elif isinstance(dq_output, str):
                    data_query_markdown = dq_output

                data_query_markdown = (data_query_markdown or "").strip()

                if data_query_markdown:
                    tone = "neutral"
                    target_audience = exec_state.get("target_audience") or getattr(ctx, "target_audience", None)

                    self._set_ctx_final_text(ctx, data_query_markdown)

                    ctx.add_agent_output(
                        agent_name=self.name,
                        logical_name="final",
                        content=data_query_markdown,
                        role="assistant",
                        action="answer",
                        intent="informational",
                        meta={
                            "agent": self.name,
                            "tone": tone,
                            "target_audience": target_audience,
                            "role_identity_question": bool(role_identity_q),
                            "bypass_llm": True,
                            "reason": "data_query_short_circuit",
                        },
                    )

                    self._store_structured_final(
                        ctx,
                        data_query_markdown,
                        exec_state=exec_state,
                        tone=tone,
                        target_audience=target_audience,
                    )

                    approx_tokens = len(data_query_markdown.split())
                    ctx.add_agent_token_usage(
                        agent_name=self.name,
                        input_tokens=0,
                        output_tokens=approx_tokens,
                        total_tokens=approx_tokens,
                    )

                    self._mark_completed(ctx)
                    return ctx

            system_prompt, user_prompt = self._compose_prompt(ctx)

            if role_identity_q:
                system_prompt = (
                    system_prompt
                    + "\n\nCRITICAL SAFETY RULE (ROLE IDENTITY): "
                    "If the user asks who currently holds a role (e.g., superintendent, principal, "
                    "mayor, president, CEO, etc.), you MUST NOT guess or invent a person's name. "
                    "Only state a name if it appears explicitly in provided documents/retrieved context. "
                    "If not stated, say you cannot confirm and suggest an official source. Do not speculate."
                )

            llm = self._resolve_llm(ctx)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = await llm.ainvoke(messages)

            formatted_text = coerce_llm_text(response).strip()
            final_answer = self._strip_metadata_block(formatted_text)

            # ✅ guarantee ctx["final"] is the final string
            self._set_ctx_final_text(ctx, final_answer)

            tone: str = "neutral"
            classifier_profile = (
                exec_state.get("classifier_profile")
                or exec_state.get("classifier_result")
                or exec_state.get("task_classification")
                or exec_state.get("classifier")
                or {}
            )
            if isinstance(classifier_profile, dict):
                upstream_tone = classifier_profile.get("tone")
                if isinstance(upstream_tone, str) and upstream_tone.strip():
                    tone = upstream_tone.strip()

            target_audience: Optional[str] = exec_state.get("target_audience") or getattr(ctx, "target_audience", None)

            ctx.add_agent_output(
                agent_name=self.name,
                logical_name="final",
                content=final_answer,
                role="assistant",
                action="answer",
                intent="informational",
                meta={
                    "agent": self.name,
                    "original_answer": formatted_text,
                    "tone": tone,
                    "target_audience": target_audience,
                    "role_identity_question": bool(role_identity_q),
                },
            )

            self._store_structured_final(
                ctx,
                final_answer,
                exec_state=exec_state,
                tone=tone,
                target_audience=target_audience,
            )

            input_tokens = getattr(response, "input_tokens", 0) or 0
            output_tokens = getattr(response, "output_tokens", 0) or 0
            total_tokens = getattr(response, "tokens_used", 0) or 0
            ctx.add_agent_token_usage(
                agent_name=self.name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

            self._mark_completed(ctx)
            return ctx

        except Exception as e:
            self._mark_failed(ctx, str(e))
            logger.error(f"[{self.name}] Execution failed: {str(e)}", exc_info=True)
            raise
