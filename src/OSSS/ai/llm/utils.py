# OSSS/ai/llm/utils.py
import asyncio
from typing import Any

async def call_llm_text(llm: Any, prompt: str) -> Any:
    """
    Call an LLM wrapper that might accept either:
      - messages: List[{"role": "...", "content": "..."}]  (preferred)
      - prompt: str                                       (fallback)

    Returns raw provider response (whatever the wrapper returns).
    """
    messages = [{"role": "user", "content": prompt}]

    # 1) Preferred: async messages API (your OpenAIChatLLM.ainvoke)
    if hasattr(llm, "ainvoke"):
        try:
            return await llm.ainvoke(messages)
        except TypeError:
            return await llm.ainvoke(prompt)
        except Exception:
            try:
                return await llm.ainvoke(prompt)
            except Exception:
                raise

    # 2) Sync messages API (your OpenAIChatLLM.invoke) - run directly
    if hasattr(llm, "invoke"):
        try:
            return llm.invoke(messages)
        except TypeError:
            return llm.invoke(prompt)
        except Exception:
            try:
                return llm.invoke(prompt)
            except Exception:
                raise

    # 3) Sync generate(prompt) - run in thread
    if hasattr(llm, "generate"):
        def _call_generate() -> Any:
            return llm.generate(prompt, stream=False)
        return await asyncio.to_thread(_call_generate)

    # 4) Compatibility: chat(prompt/messages)
    if hasattr(llm, "chat"):
        try:
            return await llm.chat(prompt)
        except TypeError:
            return await llm.chat(messages)
        except Exception:
            try:
                return await llm.chat(messages)
            except Exception:
                raise

    # 5) Compatibility: acomplete(prompt)
    if hasattr(llm, "acomplete"):
        return await llm.acomplete(prompt)

    raise AttributeError(f"Unsupported LLM interface: {type(llm).__name__}")
