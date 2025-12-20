# OSSS/ai/llm/utils.py
import asyncio
from typing import Any, Dict, List, Optional


async def call_llm_text(
    llm: Any,
    prompt: Optional[str] = None,
    *,
    messages: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.0,
    extra_json: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Call an LLM wrapper that might accept either:
      - messages: List[{"role": "...", "content": "..."}]  (preferred)
      - prompt: str                                       (fallback)

    This function keeps backward-compatibility with:
        await call_llm_text(llm, "some prompt")

    And adds support for:
        await call_llm_text(llm, messages=[...], temperature=0.0, extra_json={"format":"json"})

    Returns raw provider response (whatever the wrapper returns).
    """
    if messages is None:
        if prompt is None:
            raise ValueError("call_llm_text requires either 'prompt' or 'messages'")
        messages = [{"role": "user", "content": prompt}]
    else:
        # still allow prompt to be None if messages were provided
        if prompt is None:
            # keep a best-effort prompt string for wrappers that ONLY accept prompt
            # (we'll use the last user message content if possible)
            try:
                prompt = next(
                    (m.get("content") for m in reversed(messages) if m.get("role") == "user"),
                    None,
                )
            except Exception:
                prompt = None

    # ---- helper: try a callable with various argument shapes ----
    async def _try_async_call(fn: Any) -> Any:
        # Most preferred: messages + temperature + extra_json
        try:
            return await fn(messages=messages, temperature=temperature, extra_json=extra_json)
        except TypeError:
            pass

        # Next: messages + temperature
        try:
            return await fn(messages=messages, temperature=temperature)
        except TypeError:
            pass

        # Next: messages only
        try:
            return await fn(messages)
        except TypeError:
            pass

        # Fallback: prompt + temperature + extra_json
        if prompt is not None:
            try:
                return await fn(prompt=prompt, temperature=temperature, extra_json=extra_json)
            except TypeError:
                pass

            # Fallback: prompt + temperature
            try:
                return await fn(prompt=prompt, temperature=temperature)
            except TypeError:
                pass

            # Fallback: prompt only (positional)
            try:
                return await fn(prompt)
            except TypeError:
                pass

        raise

    def _try_sync_call(fn: Any) -> Any:
        # Most preferred: messages + temperature + extra_json
        try:
            return fn(messages=messages, temperature=temperature, extra_json=extra_json)
        except TypeError:
            pass

        # Next: messages + temperature
        try:
            return fn(messages=messages, temperature=temperature)
        except TypeError:
            pass

        # Next: messages only
        try:
            return fn(messages)
        except TypeError:
            pass

        # Fallbacks: prompt forms
        if prompt is not None:
            try:
                return fn(prompt=prompt, temperature=temperature, extra_json=extra_json)
            except TypeError:
                pass

            try:
                return fn(prompt=prompt, temperature=temperature)
            except TypeError:
                pass

            try:
                return fn(prompt)
            except TypeError:
                pass

        raise

    # 1) Preferred: async messages API (your OpenAIChatLLM.ainvoke)
    if hasattr(llm, "ainvoke"):
        try:
            return await _try_async_call(llm.ainvoke)
        except Exception:
            # last-resort fallback for older wrappers that only accept a single arg
            if prompt is not None:
                try:
                    return await llm.ainvoke(prompt)
                except Exception:
                    pass
            raise

    # 2) Sync messages API (your OpenAIChatLLM.invoke)
    if hasattr(llm, "invoke"):
        try:
            return _try_sync_call(llm.invoke)
        except Exception:
            if prompt is not None:
                try:
                    return llm.invoke(prompt)
                except Exception:
                    pass
            raise

    # 3) Sync generate(prompt) - run in thread
    if hasattr(llm, "generate"):
        def _call_generate() -> Any:
            # best effort: some wrappers accept temperature, etc; most won't
            try:
                return llm.generate(prompt, stream=False, temperature=temperature, extra_json=extra_json)
            except TypeError:
                return llm.generate(prompt, stream=False)

        if prompt is None:
            raise ValueError("llm.generate requires a prompt string, but none could be derived from messages")
        return await asyncio.to_thread(_call_generate)

    # 4) Compatibility: chat(...)
    if hasattr(llm, "chat"):
        # chat is often async in your codebase, but we’ll handle both.
        chat_fn = llm.chat
        if asyncio.iscoroutinefunction(chat_fn):
            try:
                return await _try_async_call(chat_fn)
            except Exception:
                # fallback ordering (some wrappers are chat(prompt) only)
                if prompt is not None:
                    try:
                        return await chat_fn(prompt)
                    except Exception:
                        pass
                raise
        else:
            try:
                return _try_sync_call(chat_fn)
            except Exception:
                if prompt is not None:
                    try:
                        return chat_fn(prompt)
                    except Exception:
                        pass
                raise

    # 5) Compatibility: acomplete(prompt)
    if hasattr(llm, "acomplete"):
        if prompt is None:
            raise ValueError("llm.acomplete requires a prompt string, but none could be derived from messages")
        # best effort: pass temperature / extra_json if supported
        try:
            return await llm.acomplete(prompt=prompt, temperature=temperature, extra_json=extra_json)
        except TypeError:
            try:
                return await llm.acomplete(prompt=prompt, temperature=temperature)
            except TypeError:
                return await llm.acomplete(prompt)

    raise AttributeError(f"Unsupported LLM interface: {type(llm).__name__}")
