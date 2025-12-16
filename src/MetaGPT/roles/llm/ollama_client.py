from __future__ import annotations

import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

import httpx
from httpx import HTTPStatusError

logger = logging.getLogger(__name__)

def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    """
    Convert chat-style messages into a single prompt string suitable for /api/generate.
    """
    lines: List[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "") or ""
        if role == "system":
            lines.append(f"System: {content}")
        elif role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"{role.capitalize()}: {content}")
    return "\n\n".join(lines) + "\n\nAssistant:"

class OllamaChatClient:
    """
    Async client for calling a local Ollama server.

    Strategy:
      1) Sanitize base_url down to scheme://host:port.
      2) Try /api/chat (newer Ollama versions).
      3) If /api/chat returns 404, fall back to /api/generate.
    """

    def __init__(
        self,
        base_url: str = "http://host.containers.internal:11434",
        model: str = "llama3.1",
        timeout: float = 60.0,
    ) -> None:
        # Strip any extra path, keep only scheme://host:port
        parsed = urlparse(base_url)
        if parsed.scheme and parsed.netloc:
            self.base_root = f"{parsed.scheme}://{parsed.netloc}"
        else:
            # Fallback: remove any /api... suffix if present
            self.base_root = base_url.split("/api", 1)[0].rstrip("/")

        self.model = model
        self.timeout = timeout

        logger.info(
            "OllamaChatClient initialized with base_url=%s -> base_root=%s model=%s",
            base_url,
            self.base_root,
            self.model,
        )

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Perform a chat-like completion with Ollama, returning the assistant's content.
        """
        prompt = _messages_to_prompt(messages)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # ---- 1) Try /api/chat ----
            chat_url = f"{self.base_root}/api/chat"
            chat_payload: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": 2048,

            }


            logger.info(
                "OllamaChatClient.chat -> %s model=%s payload_preview=%r",
                chat_url,
                self.model,
                repr(chat_payload)[:300],
            )

            try:
                resp = await client.post(chat_url, json=chat_payload)
                logger.info(
                    "OllamaChatClient.chat <- status=%s body_preview=%r",
                    resp.status_code,
                    resp.text[:500],
                )
                resp.raise_for_status()

                data = resp.json()
                msg = data.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, str):
                    logger.warning(
                        "OllamaChatClient.chat: unexpected /api/chat schema: %r",
                        data,
                    )
                    return "(Ollama /api/chat returned an unexpected message schema.)"
                return content

            except HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else None
                if status == 404:
                    logger.warning(
                        "OllamaChatClient.chat: /api/chat returned 404, "
                        "falling back to /api/generate",
                    )
                else:
                    logger.exception("OllamaChatClient.chat HTTP error on /api/chat")
                    raise RuntimeError(f"Ollama chat HTTP error (chat): {e}") from e
            except Exception as e:
                logger.exception("OllamaChatClient.chat unexpected error on /api/chat")
                raise RuntimeError(f"Ollama chat unexpected error (chat): {e}") from e

            # ---- 2) Fallback: /api/generate ----
            gen_url = f"{self.base_root}/api/generate"
            gen_payload: Dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "max_tokens": 2048,

            }

            logger.info(
                "OllamaChatClient.chat (fallback) -> %s model=%s prompt_preview=%r",
                gen_url,
                self.model,
                repr(prompt)[:300],
            )

            try:
                resp2 = await client.post(gen_url, json=gen_payload)
                logger.info(
                    "OllamaChatClient.chat (fallback) <- status=%s body_preview=%r",
                    resp2.status_code,
                    resp2.text[:500],
                )
                resp2.raise_for_status()
            except Exception as e:
                logger.exception("OllamaChatClient.chat HTTP error on /api/generate")
                raise RuntimeError(f"Ollama chat HTTP error (generate): {e}") from e

            data2 = resp2.json()
            content2 = data2.get("response")
            if not isinstance(content2, str):
                logger.warning(
                    "OllamaChatClient.chat: unexpected /api/generate schema: %r",
                    data2,
                )
                return "(Ollama /api/generate returned an unexpected message schema.)"

            return content2