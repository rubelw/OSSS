# OSSS/ai/llm/openai.py
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, TypeVar, Union, cast

import openai
from openai import Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam
from pydantic import BaseModel

from OSSS.ai.exceptions import (
    LLMAuthError,
    LLMContextLimitError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from OSSS.ai.observability import get_logger, get_observability_context

from .llm_interface import LLMInterface, LLMResponse

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
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.api_key = api_key
        self._model: str = (model or "").strip() or "gpt-4"
        self.base_url: Optional[str] = base_url

        self._default_extra_body: Dict[str, Any] = (
            dict(extra_body) if isinstance(extra_body, dict) else {}
        )

        # Detect Ollama-ish base_url (commonly :11434)
        self._is_ollama = bool(base_url) and ("11434" in (base_url or ""))

        # For Ollama proxies, prefer no SDK retries (avoid duplicated calls)
        if self._is_ollama and max_retries > 0:
            max_retries = 0

        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("model must be a non-empty string")
        self._model = value.strip()

    def _handle_openai_error(self, e: Exception) -> None:
        err_type = type(e).__name__
        message = str(e) or err_type

        status_code = getattr(e, "status_code", None)
        resp = getattr(e, "response", None)
        if status_code is None and resp is not None:
            status_code = getattr(resp, "status_code", None)

        AuthenticationError = getattr(openai, "AuthenticationError", None)
        RateLimitError = getattr(openai, "RateLimitError", None)
        APITimeoutError = getattr(openai, "APITimeoutError", None)
        BadRequestError = getattr(openai, "BadRequestError", None)
        NotFoundError = getattr(openai, "NotFoundError", None)
        APIConnectionError = getattr(openai, "APIConnectionError", None)
        InternalServerError = getattr(openai, "InternalServerError", None)

        if AuthenticationError and isinstance(e, AuthenticationError):
            raise LLMAuthError(message=message, llm_provider="openai", error_code="auth_error", cause=e)

        if RateLimitError and isinstance(e, RateLimitError):
            raise LLMRateLimitError(message=message, llm_provider="openai", error_code="rate_limit", cause=e)

        if APITimeoutError and isinstance(e, APITimeoutError):
            raise LLMTimeoutError(message=message, llm_provider="openai", error_code="timeout", cause=e)

        if APIConnectionError and isinstance(e, APIConnectionError):
            raise LLMServerError(message=message, llm_provider="openai", error_code="connection_error", cause=e)

        if NotFoundError and isinstance(e, NotFoundError):
            raise LLMModelNotFoundError(message=message, llm_provider="openai", error_code="model_not_found", cause=e)

        if BadRequestError and isinstance(e, BadRequestError):
            msg_l = message.lower()
            if "context length" in msg_l or "maximum context" in msg_l or "too many tokens" in msg_l:
                raise LLMContextLimitError(message=message, llm_provider="openai", error_code="context_limit", cause=e)
            raise LLMError(message=f"OpenAI bad request: {message}", llm_provider="openai", error_code="bad_request", cause=e)

        if InternalServerError and isinstance(e, InternalServerError):
            raise LLMServerError(message=message, llm_provider="openai", error_code="server_error", cause=e)

        # Fallback by status
        if status_code == 401 or status_code == 403:
            raise LLMAuthError(message=message, llm_provider="openai", error_code="auth_error", cause=e)
        if status_code == 404:
            raise LLMModelNotFoundError(message=message, llm_provider="openai", error_code="not_found", cause=e)
        if status_code == 408:
            raise LLMTimeoutError(message=message, llm_provider="openai", error_code="timeout", cause=e)
        if status_code == 429:
            raise LLMRateLimitError(message=message, llm_provider="openai", error_code="rate_limit", cause=e)
        if isinstance(status_code, int) and 500 <= status_code <= 599:
            raise LLMServerError(message=message, llm_provider="openai", error_code=f"http_{status_code}", cause=e)

        raise LLMError(message=f"OpenAI error ({err_type}): {message}", llm_provider="openai", error_code="openai_error", cause=e)

    def _coerce_kwargs_for_provider(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(kwargs)
        force_json = bool(out.pop("force_json", False))

        merged_extra_body: Dict[str, Any] = {}
        if self._default_extra_body:
            merged_extra_body.update(self._default_extra_body)

        if isinstance(out.get("extra_body"), dict):
            merged_extra_body.update(cast(Dict[str, Any], out["extra_body"]))

        rf = out.get("response_format")
        wants_json_object = force_json or (isinstance(rf, dict) and rf.get("type") == "json_object")

        # Ollama OpenAI-compat typically uses extra_body {"format":"json"} not response_format
        if self._is_ollama and wants_json_object:
            merged_extra_body.setdefault("format", "json")
            out.pop("response_format", None)

        if merged_extra_body:
            out["extra_body"] = merged_extra_body
        else:
            out.pop("extra_body", None)

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
            logger.debug(
                "Making LLM call",
                model=self.model,
                stream=stream,
                agent_name=obs_context.agent_name if obs_context else None,
            )

            safe_kwargs = self._coerce_kwargs_for_provider(dict(kwargs))

            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                **safe_kwargs,
            )

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
                self._handle_openai_error(e)  # raises

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
            response = self._chat_completion(messages=messages, stream=stream, on_log=on_log, **kwargs)

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
        text = completion.choices[0].message.content or ""
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
            raw=completion,
        )

    def invoke(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[OpenAIInvokeResult, Iterator[str]]:
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

    async def ainvoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> LLMResponse:
        def _call() -> LLMResponse:
            system_prompt: Optional[str] = None
            user_parts: List[str] = []

            for m in messages:
                role = m.get("role")
                if role == "system" and system_prompt is None:
                    system_prompt = m.get("content", "")
                elif role == "user":
                    user_parts.append(m.get("content", ""))
                elif role == "assistant":
                    user_parts.append(f"(assistant context)\n{m.get('content', '')}")

            prompt = "\n\n".join([p for p in user_parts if p]).strip()

            return cast(
                LLMResponse,
                self.generate(
                    prompt,
                    system_prompt=system_prompt,
                    stream=False,
                    **kwargs,
                ),
            )

        return await asyncio.to_thread(_call)
