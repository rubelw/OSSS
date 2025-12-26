# OSSS/ai/llm/llm_interface.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Protocol, Union


@dataclass
class LLMResponse:
    text: str
    tokens_used: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model_name: Optional[str] = None
    finish_reason: Optional[str] = None
    raw: Any = None


class LLMInterface(Protocol):
    """Provider-agnostic interface for OSSS LLM backends."""

    @property
    def model(self) -> str: ...

    @model.setter
    def model(self, value: str) -> None: ...

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        on_log: Optional[Any] = None,
        **kwargs: Any,
    ) -> Union[LLMResponse, Iterator[str]]: ...

    def invoke(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[Any, Iterator[str]]: ...

    async def ainvoke(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse: ...
