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
from typing import Any, Dict, Optional, List, Tuple, Iterable

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.utils.llm_text import coerce_llm_text

# ✅ use factory so request-level use_rag/top_k can apply
from OSSS.ai.llm.factory import LLMFactory

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
    write_output_alias: bool = False

    def __init__(self, llm: Optional[LLMInterface] = None, name: str = "final", **kwargs: Any) -> None:
        super().__init__(name=name, **kwargs)
        self.llm: Optional[LLMInterface] = llm

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
        if "refined query" in t and ("contextual information" in t or "revised query" in t or "original query" in t):
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

        This is intentionally conservative but covers both "who is" and
        "is <person> the <role>" patterns.
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

        # Pattern B: "is <something> the <role>" (e.g., "is scott blum the superintendent at ...")
        if t.startswith("is ") and any(f" the {kw}" in t for kw in _ROLE_IDENTITY_KEYWORDS):
            return True

        return False

    # -----------------------
    # trace/log discovery (generic helpers)
    # -----------------------

    def _iter_dictish_records(self, obj: Any) -> Iterable[Dict[str, Any]]:
        """
        Recursively yield dict-like trace/event records.

        Handles structures like:
          - dict (single record)
          - list/tuple of dicts
          - dict of agent -> [records...]
            e.g. {"refiner": [ {...}, {...} ], "final": [ {...} ]}
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
        We don't assume exact attribute names: we scan vars(ctx) and execution_state.
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

        # 3) common explicit keys (in case introspection misses)
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
        This lets FINAL see the full markdown from the RefinerAgent even if it's
        not explicitly placed on ctx.refiner_snippet.
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

        We prefer:
        - execution_state["original_query"] if it exists and is not refiner-ish.
        - traces from 'refiner' or 'classifier' where 'input' is a string
        - and which do NOT look like refiner markdown headings.
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

        Heuristics:
        - Prefer lines starting with 'Improved Query' or 'Refined Query'
        - Otherwise, fall back to the last line that contains a '?'
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

        Priority order:
        1) execution_state["user_question"] (node-wrapper "argument" override).
        2) Original query recovered from traces (refiner/classifier input).
        3) execution_state["original_query"] / ["raw_query"] / ["user_question"] / ["raw_query"]...
        4) direct ctx attributes (legacy/back-compat).
        5) ctx.query itself (if present and not refiner-ish).
        6) Question-like lines parsed from refiner_text.
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
                "user_query",  # still leave here for legacy, after the override above
                "user_query",
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
                    # split on '**input:**' case-insensitively
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

        Priority:
        1) execution_state["refiner_full_text"]
        2) execution_state["agent_outputs"]["refiner"] / ["outputs"]["refiner"]
        3) ctx.get_agent_output("refiner"), if available
        4) Latest trace entry with an 'output' string (we don't require an 'agent' field).
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

        Canonical storage (Option A) should set:
          ctx.execution_state["execution_config"] = <effective config dict>

        In OSSS today, "effective config" might be either:
          - the true execution_config dict (already flattened), OR
          - the full request config that *contains* an "execution_config" key.

        This function:
          1) prefers the canonical key,
          2) unwraps nested {"execution_config": {...}} when present,
          3) falls back to a few legacy/transitional keys.
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

    # -----------------------
    # prompt helpers
    # -----------------------

    def _build_prompt(
            self,
            user_question: str,
            refiner_text: str,
            rag_present: bool,
            rag_section: str,
    ) -> str:
        """
        Build the FINAL agent prompt.

        - rag_present controls the RAG_SNIPPET_PRESENT flag.
        - rag_section is either the real RAG snippet or the fallback
          "No relevant context found..." message.
        """
        parts: List[str] = []
        parts.append("You are the FINAL agent for OSSS.")
        parts.append("Your job: produce a concise, well-formatted answer for the end user.")
        parts.append("")

        # ✅ Truthful flag based on whether we actually have a non-empty RAG snippet
        parts.append(f"RAG_SNIPPET_PRESENT: {str(rag_present)}")
        parts.append("")

        parts.append("Rules:")
        parts.append("- Use retrieved context if available.")
        parts.append("- Do not claim you used retrieved context if none is provided.")
        parts.append(
            "- If you cannot confidently identify the correct entity, say what is ambiguous and what you would need.")
        parts.append("- Prefer bullet points and clear sections when helpful.")
        parts.append("- Never invent or guess the name of a real person.")
        parts.append(
            "- If the question asks who currently holds a real-world role "
            "(e.g., superintendent, principal, mayor, director, etc.) and the "
            "retrieved context above does not explicitly name that person, you must say "
            "you don't know and recommend checking an official source instead of guessing."
        )
        parts.append(
            "- When RAG_SNIPPET_PRESENT is false, you are not allowed to answer such role-identity "
            "questions with a specific person's name."
        )
        parts.append("")

        uq = (user_question or "").strip()
        parts.append("USER QUESTION:")
        parts.append(uq or "[missing user question]")

        if refiner_text and refiner_text.strip() and refiner_text.strip() != uq:
            parts.append("")
            parts.append("REFINER CONTEXT (may help disambiguate / improve search terms):")
            parts.append(refiner_text.strip())

        # ✅ Always include a RAG section, but its *content* may be the fallback string
        parts.append("")
        parts.append("RETRIEVED CONTEXT (RAG):")
        parts.append(rag_section)

        parts.append("")
        parts.append("Now produce the final answer.")
        return "\n".join(parts)

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

    async def run(self, ctx: AgentContext) -> AgentContext:
        """
        FinalAgent.run(ctx) – prepares the final answer after processing the query and context.
        """
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

            # ✅ Build prompt using rag_present + rag_section
            prompt = self._build_prompt(
                user_question=user_question,
                refiner_text=refiner_text,
                rag_present=rag_present,
                rag_section=rag_section,
            )

            # Invoke LLM and process the final answer
            llm = self._resolve_llm(ctx)
            response = await llm.ainvoke([{"role": "user", "content": prompt}])

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
