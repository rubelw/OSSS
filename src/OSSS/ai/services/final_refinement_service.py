#!/usr/bin/env python3
# src/OSSS/ai/services/final_refinement_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from OSSS.ai.observability import get_logger
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.utils.llm_text import coerce_llm_text

logger = get_logger(__name__)


@dataclass
class FinalRefinementResult:
    """
    Result from the final response refinement pass.
    """
    original: str
    refined: str
    changed: bool
    suggestions: List[str]
    error: Optional[str] = None


class FinalRefinementService:
    """
    Service to do a last-pass refinement on the final answer using an LLM.

    Responsibilities:
    - Take the original final answer (from FinalAgent or earlier agents)
    - Optionally see the original user question + extra context
    - Use an LLM to:
        * improve clarity
        * tighten wording
        * keep facts grounded in the original answer
        * keep code blocks and markdown formatting
    - Return a structured result (original + refined + metadata)

    This keeps orchestration / FinalAgent logic clean and makes refinement
    easy to toggle or adjust later.
    """

    def __init__(
        self,
        *,
        style_hint: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        """
        :param style_hint: Optional free-form description of desired style
                           (e.g. 'concise', 'friendly', 'for school admins').
        :param enabled: If False, service is a no-op and returns original text.
        """
        self.style_hint = style_hint
        self.enabled = enabled

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for the refinement pass.
        """
        style_line = ""
        if self.style_hint:
            style_line = f"\n- Writing style: {self.style_hint}."

        return (
            "You are a careful editor for an AI assistant's final answer.\n\n"
            "Your job is to refine the answer for clarity and usefulness while:\n"
            "- Preserving all factual content from the original answer.\n"
            "- Preserving any code blocks, SQL, JSON, and technical details.\n"
            "- Preserving any tables and markdown where possible.\n"
            "- Fixing grammar, wording, and structure.\n"
            "- Making it slightly more concise and easier to scan.\n"
            "- If the original answer is already clear, return it with only "
            "minor improvements.\n"
            f"{style_line}\n\n"
            "IMPORTANT:\n"
            "- Do NOT introduce new facts that are not directly supported by the original answer.\n"
            "- If something is ambiguous or missing, you may explicitly say so, "
            "but do not invent details.\n"
            "- Return ONLY the refined answer, no explanations of what you changed."
        )

    def _build_messages(
        self,
        *,
        user_query: str,
        original_answer: str,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """
        Build chat messages for the refinement LLM call.

        extra_context can include things like:
        - data_query_result
        - RAG snippets
        - execution_state metadata (sanitized)
        but is optional; often you just need question + original answer.
        """
        system_prompt = self._build_system_prompt()

        user_parts = [
            "Here is the original user question:",
            "",
            user_query,
            "",
            "Here is the current draft of the assistant's final answer:",
            "",
            original_answer,
        ]

        if extra_context:
            import json
            user_parts.extend(
                [
                    "",
                    "Optional extra context (metadata, not user-visible):",
                    "```json",
                    json.dumps(extra_context, indent=2, default=str),
                    "```",
                ]
            )

        user_content = "\n".join(user_parts)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def refine(
        self,
        *,
        user_query: str,
        original_answer: str,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> FinalRefinementResult:
        """
        Main entrypoint.

        If the LLM stack is unavailable or disabled, returns the original
        answer with changed=False and an error message (best-effort).
        """
        # Short-circuit if disabled or trivial input
        if not self.enabled:
            logger.info(
                "FinalRefinementService.refine called but service is disabled; "
                "returning original answer unchanged"
            )
            return FinalRefinementResult(
                original=original_answer,
                refined=original_answer,
                changed=False,
                suggestions=[],
                error="refinement_disabled",
            )

        stripped_original = (original_answer or "").strip()
        if not stripped_original:
            logger.info(
                "FinalRefinementService.refine got empty original answer; "
                "returning unchanged"
            )
            return FinalRefinementResult(
                original=original_answer,
                refined=original_answer,
                changed=False,
                suggestions=[],
                error="empty_original_answer",
            )

        # Bootstrap LLM stack
        try:
            llm_config = OpenAIConfig.load()
            if not llm_config.api_key:
                raise ValueError("OpenAIConfig.api_key is missing or empty")

            llm = OpenAIChatLLM(
                api_key=llm_config.api_key,
                model=llm_config.model,
                base_url=llm_config.base_url,
            )
        except Exception as bootstrap_error:
            logger.warning(
                "FinalRefinementService: failed to bootstrap LLM; "
                "returning original answer unchanged: %s",
                bootstrap_error,
                exc_info=True,
            )
            return FinalRefinementResult(
                original=original_answer,
                refined=original_answer,
                changed=False,
                suggestions=[],
                error=f"llm_bootstrap_error: {bootstrap_error}",
            )

        # Build messages and call LLM
        try:
            messages = self._build_messages(
                user_query=user_query,
                original_answer=original_answer,
                extra_context=extra_context,
            )

            resp = await llm.ainvoke(messages)
            refined_text = coerce_llm_text(resp).strip()

            if not refined_text:
                # If for some reason we got an empty string, keep the original.
                logger.warning(
                    "FinalRefinementService: LLM returned empty text; "
                    "falling back to original answer"
                )
                return FinalRefinementResult(
                    original=original_answer,
                    refined=original_answer,
                    changed=False,
                    suggestions=[],
                    error="llm_empty_response",
                )

            changed = refined_text != stripped_original

            return FinalRefinementResult(
                original=original_answer,
                refined=refined_text,
                changed=changed,
                suggestions=[],
                error=None,
            )

        except Exception as exc:
            logger.error(
                "FinalRefinementService.refine failed",
                exc_info=True,
                extra={"error_type": type(exc).__name__},
            )
            return FinalRefinementResult(
                original=original_answer,
                refined=original_answer,
                changed=False,
                suggestions=[],
                error=str(exc),
            )
