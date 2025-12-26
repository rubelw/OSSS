"""
Final agent (RAG + formatted final text).

Compatibility:
- Must be callable via BaseAgent.run_with_retry(ctx)
- Therefore FinalAgent.run signature MUST be: run(self, ctx: AgentContext) -> AgentContext
- Must write final text into ctx under key "final"
"""

from __future__ import annotations

import time
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple, Iterable, Union

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.utils.llm_text import coerce_llm_text

# ✅ use factory so request-level use_rag/top_k can apply
from OSSS.ai.llm.factory import LLMFactory

# Configuration + prompt composer imports (follow SynthesisAgent pattern)
from OSSS.ai.config.agent_configs import FinalConfig
from OSSS.ai.workflows.prompt_composer import PromptComposer, ComposedPrompt

# Final-specific prompts (system + user template)
from OSSS.ai.agents.final.prompts import build_final_prompt, FINAL_SYSTEM_PROMPT

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
    """

    write_output_alias: bool = False

    def __init__(
        self,
        llm: Optional[Union[LLMInterface, str]] = "default",
        config: Optional[FinalConfig] = None,
        name: str = "final",
        **kwargs: Any,
    ) -> None:
        # Configuration system - backward compatible
        self.config: FinalConfig = config if config is not None else FinalConfig()

        # Pass timeout from config to BaseAgent (align with SynthesisAgent/HistorianAgent)
        super().__init__(
            name=name,
            timeout_seconds=self.config.execution_config.timeout_seconds,
            **kwargs,
        )

        # Prompt composition support
        self._prompt_composer = PromptComposer()
        self._composed_prompt: Optional[ComposedPrompt] = None

        # LLM instance:
        # - If "default", we rely on per-request LLMFactory based on execution_config.
        # - If an LLMInterface is passed, we honor it.
        if llm == "default":
            self.llm: Optional[LLMInterface] = None
        else:
            if llm is None:
                self.llm = None
            elif hasattr(llm, "generate") or hasattr(llm, "ainvoke"):
                self.llm = llm  # type: ignore[assignment]
            else:
                self.llm = None

        # Compose the prompt on initialization (if PromptComposer supports final)
        self._update_composed_prompt()

    # -----------------------
    # heuristics
    # -----------------------

    def _looks_like_refiner_text(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        t = text.strip().lower()
        if not t:
            return False

        # common "no-op" marker
        if t.startswith("[unchanged]"):
            return True

        # standard refined-query headings
        if t.startswith(_REFINE_PREFIXES):
            return True

        # markdowny refiner blocks
        if "refined query" in t and (
            "contextual information" in t
            or "revised query" in t
            or "original query" in t
        ):
            return True

        if t.count("\n") >= 3 and ("###" in t or "**" in t) and "refin" in t:
            return True

        if "refined" in t and ("====" in t or "----" in t):
            return True

        # prompts that explicitly mention canonicalization rules are clearly not "the user question"
        if "canonicalization rule" in t and "dcg" in t:
            return True

        return False

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
    # role-identity question detection (to avoid hallucinating people)
    # -----------------------

    def _is_role_identity_question(self, text: str) -> bool:
        """
        Detect questions like:
          - "Who is the current superintendent of ..."
          - "Who's the principal at ..."
          - "Is Scott Blum the superintendent at DCG?"
        """
        if not isinstance(text, str):
            return False

        t = text.strip().lower()
        if not t:
            return False

        has_role_keyword = any(kw in t for kw in _ROLE_IDENTITY_KEYWORDS)
        if not has_role_keyword:
            return False

        # Pattern A: explicit "who" questions
        if "who is" in t or "who's" in t or t.startswith("who "):
            return True

        # Pattern B: "is <something> the <role>"
        if t.startswith("is ") and any(f" the {kw}" in t for kw in _ROLE_IDENTITY_KEYWORDS):
            return True

        return False

    # -----------------------
    # trace/log discovery (generic helpers)
    # -----------------------

    def _iter_dictish_records(self, obj: Any) -> Iterable[Dict[str, Any]]:
        """
        Recursively yield dict-like trace/event records.
        """
        # dict case
        if isinstance(obj, dict):
            # If this dict already looks like a trace record (has input/output/agent),
            # yield it directly.
            if any(k in obj for k in ("input", "output", "agent", "agent_name", "name")):
                yield obj

            # Then descend into values
            for v in obj.values():
                if isinstance(v, (dict, list, tuple)):
                    yield from self._iter_dictish_records(v)
            return

        # list / tuple case
        if isinstance(obj, (list, tuple)):
            for x in obj:
                if isinstance(x, (dict, list, tuple)):
                    yield from self._iter_dictish_records(x)

    def _iter_trace_candidates(self, ctx: AgentContext) -> List[Any]:
        """
        Collect candidate containers that might hold trace/log/event data.
        """
        candidates: List[Any] = []

        # 1) direct attrs on ctx (introspective)
        try:
            for k, v in vars(ctx).items():
                lk = k.lower()
                if any(tok in lk for tok in ("trace", "log", "event", "history")):
                    candidates.append(v)
        except Exception:
            pass

        # 2) execution_state (introspective)
        exec_state = getattr(ctx, "execution_state", None)
        if isinstance(exec_state, dict):
            for k, v in exec_state.items():
                lk = str(k).lower()
                if any(tok in lk for tok in ("trace", "log", "event", "history")):
                    candidates.append(v)

        # 3) common explicit keys
        for name in ("traces", "trace_log", "agent_traces", "events", "logs"):
            candidates.append(getattr(ctx, name, None))
            if isinstance(exec_state, dict):
                candidates.append(exec_state.get(name))

        return candidates

    def _iter_trace_dicts(self, ctx: AgentContext) -> List[Dict[str, Any]]:
        """
        Flatten any dict-like trace/event records we can find.
        """
        out: List[Dict[str, Any]] = []
        for c in self._iter_trace_candidates(ctx):
            if c is None:
                continue
            out.extend(list(self._iter_dictish_records(c)))

        # some implementations nest lists inside dicts like {"items":[...]} or {"records":[...]}
        expanded: List[Dict[str, Any]] = []
        for rec in out:
            expanded.append(rec)
            for key in ("items", "records", "entries", "data"):
                v = rec.get(key)
                if isinstance(v, list):
                    expanded.extend([x for x in v if isinstance(x, dict)])
        return expanded

    # -----------------------
    # original query / refiner recovery
    # -----------------------

    def _extract_original_from_refiner_text(self, refiner_text: str) -> str:
        if not isinstance(refiner_text, str) or not refiner_text.strip():
            return ""
        lowered = refiner_text.lower()
        marker = "original query:"
        idx = lowered.find(marker)
        if idx == -1:
            return ""
        after = refiner_text[idx + len(marker) :].strip()
        for line in after.splitlines():
            s = line.strip()
            if s:
                return s
        return ""

    def _extract_refiner_output_from_traces(self, ctx: AgentContext) -> str:
        """
        Best-effort extraction of the latest refiner output from the agent traces.
        """
        traces = getattr(ctx, "traces", None)
        if not isinstance(traces, list):
            return ""

        # Walk backward so we prefer the latest refiner output
        for tr in reversed(traces):
            try:
                agent = (tr.get("agent") or "").lower()
                if agent and agent != "refiner":
                    continue

                # refiner output may be under "output", "content", or "text"
                out = tr.get("output")
                if isinstance(out, str) and out.strip():
                    return out.strip()

                if isinstance(out, dict):
                    for key in ("text", "content", "markdown"):
                        val = out.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
            except Exception:
                continue

        return ""

    def _extract_original_from_traces(self, ctx: AgentContext) -> str:
        """
        Try to recover the original user query from execution_state + trace logs.
        """
        exec_state = getattr(ctx, "execution_state", None)
        if isinstance(exec_state, dict):
            oq = exec_state.get("original_query")
            if isinstance(oq, str):
                oq = oq.strip()
                if oq and not self._looks_like_refiner_text(oq):
                    return oq

        traces = getattr(ctx, "traces", None) or getattr(ctx, "trace_log", None)
        if not isinstance(traces, list):
            return ""

        candidates: List[Tuple[int, str]] = []

        for t in traces:
            if not isinstance(t, dict):
                continue
            agent_name = (t.get("agent") or t.get("agent_name") or "").lower()
            inp = t.get("input")

            # Some logs put structured payloads in 'input'
            if isinstance(inp, dict):
                inp = self._pick_first_str(
                    inp.get("query"),
                    inp.get("raw_query"),
                    inp.get("original_query"),
                    inp.get("user_query"),
                    inp.get("input_query"),
                )

            if isinstance(inp, str):
                s = inp.strip()
                if not s or self._looks_like_refiner_text(s):
                    continue

                weight = 0
                if agent_name in ("refiner", "classifier"):
                    weight = 10
                candidates.append((weight, s))

        if not candidates:
            return ""

        # pick the highest-weight candidate
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    def _extract_refined_question_from_refiner(self, refiner_text: str) -> str:
        """
        Try to pull a single 'refined' question from the refiner's markdown output.
        """
        if not isinstance(refiner_text, str) or not refiner_text.strip():
            return ""

        lines = [ln.strip() for ln in refiner_text.splitlines() if ln.strip()]
        if not lines:
            return ""

        # 1) Look for '**Improved Query**: ...' or 'Improved Query: ...'
        for ln in lines:
            low = ln.lower()
            if low.startswith("**improved query**") or low.startswith("improved query:"):
                if ":" in ln:
                    # handle '**Improved Query**: question' or 'Improved Query: question'
                    return ln.split(":", 1)[1].strip()
                continue

        # 2) Look for 'Refined Query: ...'
        for ln in lines:
            low = ln.lower()
            if low.startswith("refined query:"):
                return ln.split(":", 1)[1].strip()

        # 3) Fallback: last line that looks like an actual question
        question_candidates = [ln for ln in lines if "?" in ln]
        if question_candidates:
            return question_candidates[-1].strip()

        return ""

    def _resolve_user_question(self, ctx: AgentContext, refiner_text: str = "") -> str:
        """
        Resolve the actual end-user question the FINAL agent should answer.
        """
        exec_state = getattr(ctx, "execution_state", None)

        # 1) Treat execution_state["user_question"] as the explicit override
        if isinstance(exec_state, dict):
            uq = exec_state.get("user_question")
            if isinstance(uq, str):
                uq = uq.strip()
                if uq and not self._looks_like_refiner_text(uq):
                    return uq

        # 2) Most reliable fallback: trace input
        trace_original = self._extract_original_from_traces(ctx)
        if trace_original and not self._looks_like_refiner_text(trace_original):
            return trace_original.strip()

        candidates: List[str] = []

        # 3) remaining execution_state keys
        if isinstance(exec_state, dict):
            for key in (
                "original_query",
                "raw_query",
                "user_query",  # legacy
                "initial_query",
                "input_query",
                "query_original",
                "request_query",
            ):
                v = exec_state.get(key)
                if isinstance(v, str):
                    v = v.strip()
                    if v and not self._looks_like_refiner_text(v):
                        candidates.append(v)

        # 4) direct ctx attributes
        direct_original = self._pick_first_str(
            getattr(ctx, "original_query", None),
            getattr(ctx, "raw_query", None),
            getattr(ctx, "user_query", None),
            getattr(ctx, "input_query", None),
            getattr(ctx, "query_original", None),
        )
        if direct_original and not self._looks_like_refiner_text(direct_original):
            candidates.append(direct_original)

        # 5) ctx.query itself
        raw_query = (getattr(ctx, "query", None) or "").strip()
        if raw_query and not self._looks_like_refiner_text(raw_query):
            candidates.append(raw_query)

        # 6) derive from refiner_text if needed (e.g. "* **Input:** ..." lines)
        if isinstance(refiner_text, str) and refiner_text.strip():
            lines = [ln.strip() for ln in refiner_text.splitlines() if ln.strip()]
            for ln in lines:
                low = ln.lower()

                # pattern like: * **Input:** who is DCG superintendent
                if low.startswith("* **input:**") or low.startswith("* **input :**"):
                    parts = re.split(r"\*\*input\s*:?\*\*", ln, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        q = parts[1].strip(" :")
                        if q and not self._looks_like_refiner_text(q):
                            candidates.append(q)

                # pattern like: "* **Refined Question:** Who is the superintendent of ..."
                if "refined question:" in low:
                    q = ln.split(":", 1)[-1].strip()
                    if q and not self._looks_like_refiner_text(q):
                        candidates.append(q)

        # Finally, choose the first non-empty candidate in our priority-ordered list
        return self._pick_first_str(*candidates) or ""

    def _extract_best_refiner_text(self, ctx: AgentContext) -> str:
        """
        Best-effort extraction of the full refiner output.
        """
        exec_state = getattr(ctx, "execution_state", None)
        candidates: List[str] = []

        # 1) canonical: execution_state["refiner_full_text"]
        if isinstance(exec_state, dict):
            v = exec_state.get("refiner_full_text")
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())

        # 2) execution_state["agent_outputs"]["refiner"] / ["outputs"]["refiner"]
        if isinstance(exec_state, dict):
            for key in ("agent_outputs", "outputs"):
                ao = exec_state.get(key)
                if isinstance(ao, dict):
                    v = ao.get("refiner")
                    if isinstance(v, str) and v.strip():
                        candidates.append(v.strip())

        # 3) ctx.get_agent_output("refiner") (if such a helper exists)
        get_output = getattr(ctx, "get_agent_output", None)
        if callable(get_output):
            try:
                v = get_output("refiner")
                if isinstance(v, str) and v.strip():
                    candidates.append(v.strip())
            except Exception:
                pass

        # 4) traces (walk backward so latest outputs win)
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

        # If the "best" thing we found is just a tiny heading like "**Refined Query**",
        # treat that as effectively "no refiner text".
        if best and self._looks_like_refiner_text(best) and len(best) < 120 and len(best.splitlines()) <= 2:
            return ""

        return best

    # -----------------------
    # ✅ execution_config discovery (deterministic)
    # -----------------------

    def _get_execution_config(self, ctx: AgentContext) -> Dict[str, Any]:
        """
        Deterministic retrieval of request execution_config.
        """

        def _unwrap(v: Any) -> Dict[str, Any]:
            if not isinstance(v, dict):
                return {}
            nested = v.get("execution_config")
            if isinstance(nested, dict) and nested:
                return nested
            return v

        state = getattr(ctx, "execution_state", None)
        if isinstance(state, dict):
            # ✅ Canonical key first
            v = state.get("execution_config")
            if isinstance(v, dict):
                return _unwrap(v)

            # ✅ Legacy / transitional keys (best-effort)
            for key in ("raw_request_config", "raw_execution_config", "config", "request_config"):
                vv = state.get(key)
                if isinstance(vv, dict):
                    return _unwrap(vv)

        # last resort: ctx.execution_config attribute (legacy)
        v2 = getattr(ctx, "execution_config", None)
        if isinstance(v2, dict):
            return _unwrap(v2)

        return {}

    # -----------------------
    # prompt helpers
    # -----------------------

    def _update_composed_prompt(self) -> None:
        """
        Update the composed prompt based on current configuration, if supported.

        This mirrors the SynthesisAgent/HistorianAgent pattern:
        we prefer a composed system prompt when available.
        """
        try:
            self._composed_prompt = self._prompt_composer.compose_final_prompt(
                self.config
            )
            logger.debug(
                f"[{self.name}] Prompt composed for FinalAgent with config."
            )
        except Exception as e:
            logger.warning(
                f"[{self.name}] Failed to compose FinalAgent prompt, using default: {e}"
            )
            self._composed_prompt = None

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt, using composed prompt if available, otherwise fallback.
        """
        if self._composed_prompt and self._prompt_composer.validate_composition(
            self._composed_prompt
        ):
            return self._composed_prompt.system_prompt
        else:
            logger.debug(f"[{self.name}] Using default FinalAgent system prompt (fallback)")
            return self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """
        Default system prompt for backward compatibility.
        """
        # We import FINAL_SYSTEM_PROMPT from OSSS.ai.agents.final.prompts at module import time,
        # so there is no circular dependency here.
        return FINAL_SYSTEM_PROMPT

    def _build_prompt(
        self,
        user_question: str,
        refiner_text: str,
        rag_present: bool,
        rag_section: str,
    ) -> str:
        """
        Build the FINAL agent *user* prompt.

        Priority:
        1) If PromptComposer provides a "final_prompt" template, use that.
        2) Otherwise, fall back to build_final_prompt from prompts.py.
        """
        # Try composed template first (if available)
        if self._composed_prompt:
            try:
                tmpl = self._composed_prompt.get_template("final_prompt")
            except Exception:
                tmpl = None

            if tmpl:
                try:
                    uq = (user_question or "").strip() or "[missing user question]"
                    rt = (refiner_text or "").strip()
                    rs = (rag_section or "").strip() or "No retrieved context provided."

                    return tmpl.format(
                        user_question=uq,
                        refiner_text=rt,
                        rag_present=str(bool(rag_present)),
                        rag_section=rs,
                    )
                except Exception as e:
                    logger.debug(
                        f"[{self.name}] Failed to apply composed final_prompt template: {e}"
                    )

        # Fallback: dedicated builder (same pattern as SynthesisAgent's prompts module)
        return build_final_prompt(
            user_question=user_question,
            refiner_text=refiner_text,
            rag_present=rag_present,
            rag_section=rag_section,
        )

    # -----------------------
    # bookkeeping
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
    # ✅ LLM resolution via factory + deterministic config
    # -----------------------

    def _resolve_llm(self, ctx: AgentContext) -> LLMInterface:
        # If injected explicitly (tests / overrides), honor it.
        if self.llm is not None:
            return self.llm

        execution_config = self._get_execution_config(ctx)

        # ✅ This lets request-level use_rag/top_k flow through to LLMFactory
        return LLMFactory.create(
            agent_name="final",
            execution_config=execution_config,
        )

    def update_config(self, config: FinalConfig) -> None:
        """
        Update the agent configuration and recompose prompts.
        """
        self.config = config
        self._update_composed_prompt()
        logger.info(f"[{self.name}] Configuration updated for FinalAgent")

    # -----------------------
    # main entrypoint
    # -----------------------

    async def run(self, ctx: AgentContext) -> AgentContext:
        """
        FinalAgent.run(ctx) – prepares the final answer after processing the query and context.
        """
        self._mark_started(ctx)
        try:
            exec_state = self._get_execution_state(ctx)

            # Try to get the user question from execution_state; if missing, fall back
            user_question = (exec_state.get("user_question") or "").strip()
            if not user_question:
                # Best-effort recovery using existing helpers (optional but nice)
                ref_text_for_resolution = (
                    exec_state.get("refiner_full_text")
                    or exec_state.get("refined_query")
                    or ""
                )
                recovered = self._resolve_user_question(ctx, refiner_text=ref_text_for_resolution)
                if recovered:
                    user_question = recovered

            # ✅ Use rag_snippet presence to drive the flag, not a fallback string
            rag_snippet = exec_state.get("rag_snippet")
            if isinstance(rag_snippet, str):
                rag_snippet = rag_snippet.strip()
            else:
                rag_snippet = ""

            rag_present = bool(rag_snippet)
            if rag_present:
                rag_section = rag_snippet
                logger.info(f"[{self.name}] RAG context successfully retrieved.")
            else:
                # No real RAG snippet – we *still* show a RAG section, but the flag will be False
                logger.warning(f"[{self.name}] No RAG context found, proceeding without it.")
                rag_section = "No relevant context found for this query. Please verify the query or try again."

            # Choose best refiner text to include (if any)
            refiner_text = (
                exec_state.get("refiner_full_text")
                or exec_state.get("refined_query")
                or ""
            )

            # ✅ Build user prompt using rag_present + rag_section
            user_prompt = self._build_prompt(
                user_question=user_question,
                refiner_text=refiner_text,
                rag_present=rag_present,
                rag_section=rag_section,
            )

            # ✅ Resolve system prompt (composed or default)
            system_prompt = self._get_system_prompt()

            # Invoke LLM and process the final answer
            llm = self._resolve_llm(ctx)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = await llm.ainvoke(messages)

            formatted_text = coerce_llm_text(response).strip()

            # Set the final output in context
            ctx.add_agent_output("final", formatted_text)

            # Handle token usage (best-effort)
            input_tokens = getattr(response, "input_tokens", 0) or 0
            output_tokens = getattr(response, "output_tokens", 0) or 0
            total_tokens = getattr(response, "tokens_used", 0) or 0
            ctx.add_agent_token_usage(
                agent_name=self.name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

            # Mark as completed successfully
            self._mark_completed(ctx)

            return ctx

        except Exception as e:
            self._mark_failed(ctx, str(e))
            logger.error(f"[{self.name}] Execution failed: {str(e)}", exc_info=True)
            raise
