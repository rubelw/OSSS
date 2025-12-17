import asyncio
from dataclasses import dataclass
import time
from typing import Any, Iterator, Optional, Callable, Union, cast, List, Generator, Dict, TypeVar

import openai
from openai import Stream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionChunk,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from pydantic import BaseModel

from .llm_interface import LLMInterface, LLMResponse
from OSSS.ai.exceptions import (
    LLMQuotaError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMContextLimitError,
    LLMModelNotFoundError,
    LLMServerError,
    LLMError,
)
from OSSS.ai.observability import get_logger, get_observability_context

T = TypeVar("T", bound=BaseModel)


@dataclass
class OpenAIInvokeResult:
    content: str
    raw: Any = None
    tokens_used: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model_name: Optional[str] = None
    finish_reason: Optional[str] = None


class OpenAIChatLLM(LLMInterface):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.model: Optional[str] = model
        self.base_url: Optional[str] = base_url

        # Detect Ollama-ish base_url (your logs: http://host.containers.internal:11434)
        self._is_ollama = bool(base_url) and ("11434" in (base_url or ""))

        # Strongly recommended for Ollama: disable SDK retries to avoid repeated calls
        if self._is_ollama and max_retries > 0:
            max_retries = 0

        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def _coerce_kwargs_for_provider(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make kwargs compatible across:
        - OpenAI (response_format JSON mode)
        - Ollama OpenAI-compatible endpoint (extra_body.format="json")
        """
        out = dict(kwargs)

        # Allow caller to request JSON strictly even without response_format
        force_json = bool(out.pop("force_json", False))

        # Merge/normalize extra_body (OpenAI SDK supports passing extra_body through)
        extra_body: Dict[str, Any] = {}
        if isinstance(out.get("extra_body"), dict):
            extra_body.update(out["extra_body"])

        # If caller asked OpenAI JSON mode, translate for Ollama.
        # OpenAI: response_format={"type":"json_object"}
        rf = out.get("response_format")
        wants_json_object = (
            force_json
            or (isinstance(rf, dict) and rf.get("type") == "json_object")
        )

        if self._is_ollama and wants_json_object:
            # Ollama expects {"format": "json"} in the request body
            extra_body.setdefault("format", "json")

            # Ollama may not understand response_format; remove it to be safe
            out.pop("response_format", None)

        if extra_body:
            out["extra_body"] = extra_body

        return out

    def _chat_completion(
        self,
        *,
        messages: List[ChatCompletionMessageParam],
        stream: bool,
        on_log: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Union[Stream[ChatCompletionChunk], ChatCompletion]:
        logger = get_logger("llm.openai")
        obs_context = get_observability_context()
        llm_start_time = time.time()

        try:
            assert isinstance(self.model, str), "model must be a string"

            logger.debug(
                "Making LLM call",
                model=self.model,
                stream=stream,
                agent_name=obs_context.agent_name if obs_context else None,
            )

            safe_kwargs = self._coerce_kwargs_for_provider(dict(kwargs))

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                **safe_kwargs,
            )
            return response

        except Exception as e:
            llm_duration_ms = (time.time() - llm_start_time) * 1000
            logger.error(
                f"LLM call failed: {e}",
                model=self.model,
                duration_ms=llm_duration_ms,
                error_type=type(e).__name__,
                agent_name=obs_context.agent_name if obs_context else None,
            )
            if on_log:
                on_log(f"[OpenAIChatLLM][error] {e}")

            if isinstance(e, openai.OpenAIError):
                self._handle_openai_error(cast(openai.APIError, e))  # raises
            raise LLMError(
                message=f"Unexpected error during OpenAI API call: {str(e)}",
                llm_provider="openai",
                error_code="unexpected_error",
                cause=e,
            )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        on_log: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Union[LLMResponse, Iterator[str]]:
        logger = get_logger("llm.openai")

        try:
            from OSSS.ai.diagnostics.metrics import get_metrics_collector
            metrics = get_metrics_collector()
        except ImportError:
            metrics = None

        llm_start_time = time.time()
        obs_context = get_observability_context()

        messages: List[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            assert isinstance(self.model, str), "model must be a string"

            response = self._chat_completion(
                messages=messages,
                stream=stream,
                on_log=on_log,
                **kwargs,
            )

        except openai.APIError as e:
            llm_duration_ms = (time.time() - llm_start_time) * 1000
            logger.error(
                f"LLM API call failed: {str(e)}",
                model=self.model,
                duration_ms=llm_duration_ms,
                error_type=type(e).__name__,
                agent_name=obs_context.agent_name if obs_context else None,
            )
            if metrics:
                metrics.increment_counter(
                    "llm_api_calls_failed",
                    labels={
                        "model": self.model or "unknown",
                        "agent": obs_context.agent_name if obs_context and obs_context.agent_name else "unknown",
                        "error_type": type(e).__name__,
                    },
                )
            if on_log:
                on_log(f"[OpenAIChatLLM][error] {str(e)}")
            self._handle_openai_error(e)  # raises

        except Exception as e:
            llm_duration_ms = (time.time() - llm_start_time) * 1000
            logger.error(
                f"Unexpected LLM error: {str(e)}",
                model=self.model,
                duration_ms=llm_duration_ms,
                error_type=type(e).__name__,
                agent_name=obs_context.agent_name if obs_context else None,
            )
            if metrics:
                metrics.increment_counter(
                    "llm_api_calls_failed",
                    labels={
                        "model": self.model or "unknown",
                        "agent": obs_context.agent_name if obs_context and obs_context.agent_name else "unknown",
                        "error_type": "unexpected_error",
                    },
                )
            if on_log:
                on_log(f"[OpenAIChatLLM][unexpected_error] {str(e)}")
            raise LLMError(
                message=f"Unexpected error during OpenAI API call: {str(e)}",
                llm_provider="openai",
                error_code="unexpected_error",
                cause=e,
            )

        if stream:
            stream_response = cast(Stream[ChatCompletionChunk], response)

            def token_generator() -> Generator[str, None, None]:
                for chunk in stream_response:
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    if on_log and content:
                        on_log(f"[OpenAIChatLLM][streaming] {content}")
                    yield content

            return token_generator()

        completion = cast(ChatCompletion, response)
        text = (completion.choices[0].message.content or "")
        usage = completion.usage

        tokens_used = usage.total_tokens if usage else None
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        finish_reason = completion.choices[0].finish_reason

        llm_duration_ms = (time.time() - llm_start_time) * 1000
        logger.log_llm_call(
            model=self.model or "unknown",
            tokens_used=tokens_used or 0,
            duration_ms=llm_duration_ms,
            prompt_length=len(prompt),
            response_length=len(text),
            finish_reason=finish_reason,
            agent_name=obs_context.agent_name if obs_context else None,
        )

        return LLMResponse(
            text=text,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model,
            finish_reason=finish_reason,
        )

    def invoke(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[OpenAIInvokeResult, Iterator[str]]:
        assert isinstance(self.model, str), "model must be a string"

        oai_messages = cast(List[ChatCompletionMessageParam], messages)
        safe_kwargs = self._coerce_kwargs_for_provider(dict(kwargs))

        response = self.client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            stream=stream,
            **safe_kwargs,
        )

        if stream:
            stream_response = cast(Stream[ChatCompletionChunk], response)

            def token_generator() -> Iterator[str]:
                for chunk in stream_response:
                    yield chunk.choices[0].delta.content or ""

            return token_generator()

        completion = cast(ChatCompletion, response)
        text = (completion.choices[0].message.content or "").strip()
        usage = completion.usage

        return OpenAIInvokeResult(
            content=text,
            raw=completion,
            tokens_used=usage.total_tokens if usage else None,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            model_name=self.model,
            finish_reason=completion.choices[0].finish_reason,
        )

    async def ainvoke(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        def _call() -> LLMResponse:
            system_prompt = None
            user_parts = []

            for m in messages:
                if m["role"] == "system" and system_prompt is None:
                    system_prompt = m["content"]
                elif m["role"] == "user":
                    user_parts.append(m["content"])
                elif m["role"] == "assistant":
                    user_parts.append(f"(assistant context)\n{m['content']}")

            prompt = "\n\n".join(user_parts).strip()
            return cast(LLMResponse, self.generate(prompt, system_prompt=system_prompt, stream=False, **kwargs))

        return await asyncio.to_thread(_call)

    # _handle_openai_error unchanged...
