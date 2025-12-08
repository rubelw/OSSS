# src/OSSS/ai/langchain/base.py
from __future__ import annotations
from typing import Any, Dict, Optional, Protocol
import os
import logging

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("OSSS.ai.langchain.base")

DEFAULT_MODEL = os.getenv("OSSS_LANGCHAIN_MODEL", "gpt-4.1-mini")


class LangChainAgentProtocol(Protocol):
    name: str

    async def run(self, message: str, *, session_id: Optional[str] = None) -> Dict[str, Any]:
        ...


def get_llm(model: Optional[str] = None) -> BaseChatModel:
    model_name = (model or DEFAULT_MODEL).strip()
    return ChatOpenAI(model=model_name, temperature=0.1, max_tokens=2048)


class SimpleChatAgent:
    """Generic 1-shot QA agent."""
    def __init__(self, name: str, system_prompt: str, model: Optional[str] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model

    async def run(self, message: str, *, session_id: Optional[str] = None) -> Dict[str, Any]:
        llm = get_llm(self.model)
        msgs = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=message),
        ]
        resp = await llm.ainvoke(msgs)
        text = getattr(resp, "content", str(resp))
        return {"reply": text, "agent": self.name}
