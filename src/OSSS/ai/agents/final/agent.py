# OSSS/ai/agents/final/agent.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

from OSSS.ai.llm.factory import LLMFactory
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.utils.llm_text import coerce_llm_text

from OSSS.ai.config.agent_configs import FinalConfig
from OSSS.ai.workflows.prompt_composer import ComposedPrompt, PromptComposer
from OSSS.ai.agents.final.prompts import FINAL_SYSTEM_PROMPT, build_final_prompt
from OSSS.ai.orchestration.state_schemas import FinalState

logger = get_logger(__name__)


class FinalAgent(BaseAgent):
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
            self.llm = llm if (llm is not None and (hasattr(llm, "generate") or hasattr(llm, "ainvoke"))) else None  # type: ignore[assignment]

        self._update_composed_prompt()

    # ----------------------------
    # execution_state helpers
    # ----------------------------

    def _get_execution_state(self, ctx: AgentContext) -> Dict[str, Any]:
        state = getattr(ctx, "execution_state", None)
        if not isinstance(state, dict):
            state = {}
            setattr(ctx, "execution_state", state)
        return state

    # ----------------------------
    # CRITICAL: write result where API reads it
    # ----------------------------

    def _write_answer_text(self, ctx: AgentContext, exec_state: Dict[str, Any], text_markdown: str) -> None:
        """
        ✅ This is the real fix for your logs.

        Your /api/query response is populating answer.text_markdown with "query consents"
        because it can't find the canonical final answer field and falls back to echo.

        So we write the final text into multiple canonical locations used by typical OSSS
        serializers and node wrappers.
        """
        text_markdown = (text_markdown or "").strip()

        # 1) execution_state canonical-ish fields
        exec_state["final"] = text_markdown
        exec_state["final_text_markdown"] = text_markdown
        exec_state["answer_text_markdown"] = text_markdown

        # Some serializers expect exec_state["answer"] dict
        exec_state["answer"] = {
            "text_markdown": text_markdown,
            "used_rag": bool(exec_state.get("used_rag") or exec_state.get("rag_used") or exec_state.get("rag_enabled")),
        }

        # Some wrappers store a "response" object/dict
        exec_state["response"] = exec_state.get("response") if isinstance(exec_state.get("response"), dict) else {}
        exec_state["response"]["text_markdown"] = text_markdown

        # 2) ctx “well-known” storage patterns (best-effort)
        for key in ("final", "answer", "text_markdown", "response_text", "assistant_text"):
            try:
                setter = getattr(ctx, "set", None)
                if callable(setter):
                    setter(key, text_markdown)
            except Exception:
                pass

        # 3) attribute fallbacks
        for attr in ("final", "answer", "text_markdown", "response_text"):
            try:
                setattr(ctx, attr, text_markdown)
            except Exception:
                pass

        # 4) keep your agent output trail
        try:
            ctx.add_agent_output(
                agent_name=self.name,
                logical_name="final",
                content=text_markdown,
                role="assistant",
                action="answer",
                intent="informational",
                meta={"agent": self.name, "canonical_write": True},
            )
        except Exception:
            pass

    def _store_structured_final(self, exec_state: Dict[str, Any], text: str) -> None:
        rag_snippet = exec_state.get("rag_snippet")
        rag_excerpt = rag_snippet.strip() if isinstance(rag_snippet, str) and rag_snippet.strip() else None

        final_struct: FinalState = {
            "final_answer": text,
            "used_rag": bool(exec_state.get("rag_enabled")) and bool(rag_excerpt),
            "rag_excerpt": rag_excerpt,
            "sources_used": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        structured = exec_state.get("structured_outputs")
        if not isinstance(structured, dict):
            structured = {}
            exec_state["structured_outputs"] = structured
        structured["final"] = final_struct

    # ----------------------------
    # pending_action prompt
    # ----------------------------

    def _pending_action(self, exec_state: Dict[str, Any]) -> Dict[str, Any]:
        pa = exec_state.get("pending_action")
        return pa if isinstance(pa, dict) else {}

    def _is_confirm_yes_no(self, exec_state: Dict[str, Any]) -> bool:
        pa = self._pending_action(exec_state)
        return str(pa.get("type") or "").strip().lower() == "confirm_yes_no"

    def _confirm_prompt(self, exec_state: Dict[str, Any]) -> str:
        pa = self._pending_action(exec_state)
        ctxd = pa.get("context") if isinstance(pa.get("context"), dict) else {}

        op = str(ctxd.get("operation") or "").strip().lower() or "read"
        table = (
            str(ctxd.get("table_name") or "").strip()
            or str(ctxd.get("collection") or "").strip()
        )

        if not table:
            wiz = exec_state.get("wizard")
            if isinstance(wiz, dict):
                table = str(wiz.get("table_name") or wiz.get("collection") or "").strip()
                op = str(wiz.get("operation") or op or "read").strip().lower()

        if not table:
            pq = str(pa.get("pending_question") or "").strip()
            if pq.lower().startswith("query "):
                table = pq.split(" ", 1)[1].strip()

        if table:
            if op == "read":
                return f"Confirm: run query on `{table}`? Reply **yes** or **no**."
            return f"Confirm: perform `{op}` on `{table}`? Reply **yes** or **no**."
        return "Confirm: proceed? Reply **yes** or **no**."

    def _should_bypass_llm(self, exec_state: Dict[str, Any]) -> bool:
        if self._is_confirm_yes_no(exec_state):
            return True
        pa = self._pending_action(exec_state)
        if pa.get("awaiting") is True:
            return True
        if isinstance(exec_state.get("final_markdown_override"), str) and exec_state["final_markdown_override"].strip():
            return True
        return False

    # ----------------------------
    # prompt composer + LLM
    # ----------------------------

    def _update_composed_prompt(self) -> None:
        try:
            self._composed_prompt = self._prompt_composer.compose_final_prompt(self.config)
            logger.debug("[final] Prompt composed for FinalAgent with config.")
        except Exception as e:
            logger.warning(f"[final] Failed to compose FinalAgent prompt, using default: {e}")
            self._composed_prompt = None

    def _get_system_prompt(self) -> str:
        if self._composed_prompt and self._prompt_composer.validate_composition(self._composed_prompt):
            return self._composed_prompt.system_prompt
        return FINAL_SYSTEM_PROMPT

    def _get_execution_config(self, ctx: AgentContext) -> Dict[str, Any]:
        state = getattr(ctx, "execution_state", None)
        if isinstance(state, dict):
            cfg = state.get("config")
            if isinstance(cfg, dict):
                nested = cfg.get("execution_config")
                if isinstance(nested, dict) and nested:
                    return nested
                return cfg
        v2 = getattr(ctx, "execution_config", None)
        return v2 if isinstance(v2, dict) else {}

    def _resolve_llm(self, ctx: AgentContext) -> LLMInterface:
        if self.llm is not None:
            return self.llm
        return LLMFactory.create(agent_name="final", execution_config=self._get_execution_config(ctx))

    # ----------------------------
    # main
    # ----------------------------

    async def run(self, ctx: AgentContext) -> AgentContext:
        exec_state = self._get_execution_state(ctx)

        # If confirm pending action, bypass LLM and deliver prompt
        if self._should_bypass_llm(exec_state):
            text = self._confirm_prompt(exec_state) if self._is_confirm_yes_no(exec_state) else "Please reply **yes** or **no**."
            logger.warning("[final] PROMPT-DELIVERY BYPASS HIT")  # unmistakable
            self._write_answer_text(ctx, exec_state, text)
            self._store_structured_final(exec_state, text)
            return ctx

        # Normal LLM path
        system_prompt = self._get_system_prompt()
        user_question = str(exec_state.get("user_question") or exec_state.get("question") or exec_state.get("query") or "").strip()

        rag_snippet = str(exec_state.get("rag_snippet") or "").strip()
        user_prompt = build_final_prompt(
            user_question=user_question or "[missing user question]",
            refiner_text=str(exec_state.get("refiner") or "").strip(),
            rag_present=bool(rag_snippet),
            rag_section=rag_snippet,
            original_user_question=user_question,
            data_query_markdown="",
            config=self.config,
            rag_metadata=None,
            data_query_metadata=None,
        )

        llm = self._resolve_llm(ctx)
        response = await llm.ainvoke(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )
        final_answer = coerce_llm_text(response).strip()

        self._write_answer_text(ctx, exec_state, final_answer)
        self._store_structured_final(exec_state, final_answer)
        return ctx

