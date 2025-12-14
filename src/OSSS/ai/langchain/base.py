# src/OSSS/ai/langchain/base.py
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol
import os
import logging

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("OSSS.ai.langchain.base")

# ---------------------------------------------------------------------------
# Settings / configuration
# ---------------------------------------------------------------------------

try:
    # Prefer your real settings if available
    from OSSS.config import settings as _settings  # type: ignore
    settings = _settings
except Exception:
    # Fallback for tests / local usage
    class _Settings:
        VLLM_ENDPOINT: str = os.getenv(
            "VLLM_ENDPOINT", "http://host.containers.internal:11434"
        )
        OSSS_LANGCHAIN_MODEL: str = os.getenv(
            "OSSS_LANGCHAIN_MODEL", "llama3.2-vision"
        )

    settings = _Settings()  # type: ignore

DEFAULT_MODEL = getattr(
    settings,
    "OSSS_LANGCHAIN_MODEL",
    os.getenv("OSSS_LANGCHAIN_MODEL", "llama3.2-vision"),
).strip()


class LangChainAgentProtocol(Protocol):
    name: str
    intent: str  # e.g. "incidents"
    intent_aliases: list[str] = []

    async def run(self, message: str, *, session_id: Optional[str] = None) -> Dict[str, Any]:
        ...


def _get_base_url() -> str:
    """
    Return the OpenAI-compatible base URL, always including /v1.

    This is where Ollama / vLLM exposes:
      - POST /v1/chat/completions
      - POST /v1/embeddings
    """
    base = getattr(
        settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434"
    ).rstrip("/")
    url = f"{base}/v1"
    logger.debug("LangChain base URL resolved to %s", url)
    return url


def get_llm(
    model: Optional[str] = None,
    *,
    streaming: bool = False,
) -> BaseChatModel:
    """
    Shared LangChain ChatOpenAI client that talks to your local
    Ollama / vLLM server using the OpenAI-compatible /v1 API.

    NOTE:
      - For tool-using agents, prefer streaming=False.
        (Streaming tool calls can cause the agent to return the tool-call JSON
         instead of executing the tool coroutine, depending on provider/adapter.)
    """
    model_name = (model or DEFAULT_MODEL).strip()
    base_url = _get_base_url()

    logger.info(
        "Creating LangChain ChatOpenAI client: model=%s base_url=%s streaming=%s",
        model_name,
        base_url,
        streaming,
    )

    return ChatOpenAI(
        model=model_name,
        api_key="not-used",      # Ollama/vLLM ignore this but LangChain requires it
        base_url=base_url,       # ensures /v1/chat/completions, not /chat/completions
        temperature=0.1,
        max_tokens=2048,
        streaming=streaming,
    )


class SimpleChatAgent:
    """Generic 1-shot QA agent."""
    def __init__(self, name: str, system_prompt: str, model: Optional[str] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model

    async def run(self, message: str, *, session_id: Optional[str] = None) -> Dict[str, Any]:
        # Streaming is fine here since this agent is not tool-using
        llm = get_llm(self.model, streaming=True)
        msgs = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=message),
        ]
        resp = await llm.ainvoke(msgs)
        text = getattr(resp, "content", str(resp))
        return {"reply": text, "agent": self.name}
