from __future__ import annotations

from typing import Optional, Any, Dict, List

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.context import AgentContext
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.utils.llm_text import coerce_llm_text


class AnswerSearchAgent(BaseAgent):
    def __init__(
        self,
        llm: LLMInterface,
        name: str = "answer_search",
        **kwargs: Any,
    ) -> None:
        # IMPORTANT: BaseAgent doesn't accept llm=
        super().__init__(name=name, **kwargs)
        self.llm = llm                          # ✅ store it on the instance

    async def run(self, context: AgentContext) -> AgentContext:
        query = (context.query or "").strip()

        # For now: LLM-only "answer" (no real retrieval yet)
        messages = [
            {"role": "system", "content": "Answer the user's question clearly and concisely."},
            {"role": "user", "content": query},
        ]

        resp = await self.llm.ainvoke(messages)
        answer_text = coerce_llm_text(resp).strip()

        sources: List[Dict[str, Any]] = []  # TODO: fill when you add real retrieval

        payload = {
            "ok": True,
            "type": "answer_search",
            "answer_text": answer_text,
            "sources": sources,
        }

        context.execution_state["answer_search_payload"] = payload
        context.add_agent_output(self.name, answer_text)

        # record token usage if present (matches your Refiner pattern)
        input_tokens = getattr(resp, "input_tokens", 0) or 0
        output_tokens = getattr(resp, "output_tokens", 0) or 0
        total_tokens = getattr(resp, "tokens_used", 0) or 0
        context.add_agent_token_usage(
            agent_name=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        return context
