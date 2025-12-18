# OSSS/ai/agents/guard.py
from __future__ import annotations

import json
import re
import os
import logging
from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel

from OSSS.ai.agents.base_agent import (
    BaseAgent,
    NodeType,
    NodeInputSchema,
    NodeOutputSchema,
)
from OSSS.ai.context import AgentContext
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM

from OSSS.ai.agents.guard.prompts import (
    GUARD_SYSTEM_PROMPT,
    GUARD_USER_TEMPLATE,
)


logger = logging.getLogger(__name__)


class GuardDecision(BaseModel):
    """
    Structured decision returned by the guard model.
    This is NOT the agent. The agent is GuardAgent(BaseAgent) below.
    """
    decision: Literal["allow", "block", "requires_confirmation"] = "allow"
    confidence: float = 0.5

    category: Literal[
        "ok",
        "sexual_content",
        "self_harm",
        "violence_weapons",
        "hate_harassment",
        "illegal_wrongdoing",
        "privacy_pii_minors",
        "other",
    ] = "ok"

    # short explanation for logs/telemetry (not necessarily shown to user)
    reason: str = ""

    # if block, a user-facing safe response
    safe_response: str = ""


def _extract_json(text: str) -> Dict[str, Any]:
    t = (text or "").strip()

    # Strip fenced blocks
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()

    # Fast path: pure JSON object
    if t.startswith("{") and t.endswith("}"):
        return json.loads(t)

    # Defensive: find first {...} block in a mixed string
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError(f"Guard: no JSON object found in: {t[:200]!r}")
    return json.loads(m.group(0))


def _default_safe_response() -> str:
    return (
        "I can’t help with that request. If you’re dealing with something unsafe or urgent, "
        "please talk to a trusted adult or call local emergency services."
    )


class GuardAgent(BaseAgent):
    """
    Guard agent that classifies a query for safety and policy routing.

    Produces:
      - context.agent_outputs["guard"] = <dict decision>
      - context.agent_output_meta["guard"] envelope via BaseAgent._wrap_output
      - optional structured output in context.execution_state["structured_outputs"]["guard"]
    """

    def __init__(
        self,
        llm: Optional[LLMInterface] = None,
        *,
        timeout_seconds: int = 20,
    ) -> None:
        super().__init__("guard", timeout_seconds=timeout_seconds)

        # Allow DI; otherwise build default OpenAIChatLLM from config.
        if llm is None:
            cfg = OpenAIConfig.load()
            llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

        self.llm: LLMInterface = llm

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
        # Keep consistent envelope shape with other agents
        return super()._wrap_output(
            output=output,
            intent=intent,
            tone=tone,
            action=action,
            sub_tone=sub_tone,
            content=content,
        )

    async def run(self, context: AgentContext) -> AgentContext:
        # ✅ prove which code is running (helps with LangGraph caching / stale processes)
        logger.info(f"[{self.name}] GUARD_RUN_VERSION=v3 file={__file__} pid={os.getpid()}")

        query = (context.query or "").strip()
        logger.info(f"[{self.name}] Guarding query: {query[:200]}")

        # Fast path
        if not query:
            decision = GuardDecision(
                decision="allow",
                confidence=0.5,
                category="ok",
                reason="empty_query",
            )
            return self._write_outputs(context, query, decision)

        try:
            prompt = GUARD_USER_TEMPLATE.format(query=query)
        except Exception as e:
            logger.warning(f"[{self.name}] GUARD_USER_TEMPLATE.format failed, falling back to replace: {e!r}")
            prompt = GUARD_USER_TEMPLATE.replace("{query}", query)

        # Default decision if anything goes wrong (guard should not take down the workflow)
        fallback = GuardDecision(
            decision="allow",
            confidence=0.5,
            category="other",
            reason="guard_fallback",
            safe_response="",
        )

        try:
            resp = await self.llm.ainvoke(
                [
                    {"role": "system", "content": GUARD_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            # ✅ Coerce to text, but never let coercion errors crash execution
            text: str
            try:
                from OSSS.ai.utils.llm_text import coerce_llm_text
                text = coerce_llm_text(resp)
            except Exception as e:
                logger.warning(f"[{self.name}] coerce_llm_text failed: {e!r}")

                # tolerant fallback: try common shapes, then str()
                # (some adapters return dict-like, some return objects with .text/.content)
                if isinstance(resp, dict):
                    text = (
                            resp.get("text")
                            or resp.get("content")
                            or resp.get("message")
                            or json.dumps(resp)
                    )
                else:
                    text = getattr(resp, "text", None) or getattr(resp, "content", None) or str(resp)

            text = (text or "").strip()

            # ✅ Parse + validate
            data = _extract_json(text)
            decision = GuardDecision.model_validate(data)

            if decision.decision == "block" and not decision.safe_response:
                decision.safe_response = _default_safe_response()

            logger.debug(f"[{self.name}] Guard decision: {decision.model_dump()}")

            return self._write_outputs(context, query, decision)

        except Exception as e:
            # ✅ NEVER raise from guard
            logger.warning(f"[{self.name}] Guard failed, allowing by fallback: {e!r}")
            fallback.reason = f"guard_error: {type(e).__name__}: {e}"
            return self._write_outputs(context, query, fallback)

    def _halt_workflow(self, context: AgentContext, *, reason: str, user_message: str) -> None:
        """
        Signal to the orchestrator/graph runner that execution should stop,
        and provide the user-facing response to return.
        """
        context.execution_state.setdefault("routing", {})
        context.execution_state["routing"].update(
            {
                "halt": True,
                "halt_by": self.name,
                "halt_reason": reason,
                "final_response": user_message,
            }
        )

    def _write_outputs(self, context: AgentContext, query: str, decision: GuardDecision) -> AgentContext:
        # Store structured output for downstream consumers (your orchestration_api prefers this)
        context.execution_state.setdefault("structured_outputs", {})
        context.execution_state["structured_outputs"][self.name] = decision.model_dump()

        # Store human-friendly / legacy output (string or dict). Use dict so API can serialize.
        context.add_agent_output(self.name, decision.model_dump())

        # ✅ HALT PIPELINE IF GUARD DOES NOT ALLOW
        if decision.decision != "allow":
            # Choose a safe user-facing response
            if decision.safe_response:
                final_message = decision.safe_response
            elif decision.decision == "requires_confirmation":
                final_message = (
                    "I can help with this, but I need your confirmation before proceeding. "
                    "Do you want me to continue?"
                )
            else:
                final_message = _default_safe_response()

            context.execution_state.setdefault("routing", {})
            context.execution_state["routing"].update(
                {
                    "halt": True,
                    "halt_by": self.name,
                    "halt_reason": f"guard_{decision.decision}:{decision.category}",
                    "final_response": final_message,
                }
            )

        # Envelope metadata (intent/tone/action are yours to choose;
        # action="read" is fine if guard is informational classification)
        env = self._wrap_output(
            output=decision.safe_response if decision.decision == "block" else "",
            intent="safety_check",
            tone="neutral",
            action="read",
            sub_tone=None,
        )

        # Attach useful fields to envelope so your agent_output_meta is rich
        env.update(
            {
                "decision": decision.decision,
                "confidence": float(decision.confidence),
                "category": decision.category,
                "reason": decision.reason,
                "safe_response": decision.safe_response,
            }
        )

        context.add_agent_output_envelope(self.name, env)
        context.log_trace(self.name, input_data=query, output_data=decision.model_dump())
        return context

    def define_node_metadata(self) -> Dict[str, Any]:
        return {
            "node_type": NodeType.PROCESSOR,
            "dependencies": [],
            "description": "Safety / policy guard. Classifies query and returns allow/block/confirm decision.",
            "inputs": [
                NodeInputSchema(
                    name="context",
                    description="Agent context containing the user query",
                    required=True,
                    type_hint="AgentContext",
                )
            ],
            "outputs": [
                NodeOutputSchema(
                    name="context",
                    description="Updated context with guard decision",
                    type_hint="AgentContext",
                )
            ],
            "tags": ["guard", "agent", "policy", "safety"],
        }
