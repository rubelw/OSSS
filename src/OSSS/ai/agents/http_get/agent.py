from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import httpx

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.observability import get_logger
from .models import HttpGetResult

logger = get_logger(__name__)


class HttpGetAgent(BaseAgent):
    """
    Agent that performs an HTTP GET against a FastAPI endpoint and stores results in context.

    Typical uses:
    - fetch reference data before other agents
    - pull tools/results from internal services
    - enrich query context with structured payloads
    """

    name = "http_get"

    def __init__(
            self,
            *,
            base_url: str,
            path: str,
            timeout_s: float = 10.0,
            headers: Optional[Dict[str, str]] = None,
            query_params: Optional[Dict[str, Any]] = None,
            store_key: str = "http_get_result",
            auth_token_env: Optional[str] = None,
    ) -> None:
        super().__init__(name=self.name, timeout_seconds=timeout_s)

        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"
        self.timeout_s = timeout_s
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.store_key = store_key
        self.auth_token_env = auth_token_env

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(
            node_type="tool",
            agent_name="HttpGetAgent",
            dependencies=[],
        )

    async def run(self, context: AgentContext) -> AgentContext:
        exec_cfg: Dict[str, Any] = (context.execution_state.get("execution_config", {}) or {})
        headers = dict(self.headers)

        if self.auth_token_env:
            token = os.getenv(self.auth_token_env)
            if token:
                headers.setdefault("Authorization", f"Bearer {token}")

        params = dict(self.query_params)
        params.update(exec_cfg.get("http_query_params", {}))

        url = f"{self.base_url}{self.path}"

        # Log the request details
        logger.debug("Sending HTTP GET request", extra={
            "url": url,
            "headers": headers,
            "query_params": params,
        })

        start = time.time()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.get(url, params=params, headers=headers)
        elapsed_ms = int((time.time() - start) * 1000)

        parsed_json: Any = None
        text: Optional[str] = None
        try:
            # Log the raw response body before attempting to parse as JSON
            logger.debug("Received response", extra={
                "response_text": resp.text[:500],  # Log up to 500 characters for brevity
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
            })

            # Check if the response is actually JSON
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                logger.debug("Response is identified as JSON", extra={"url": str(resp.request.url)})
                parsed_json = resp.json()
            else:
                logger.warning("Received non-JSON response", extra={
                    "response_text": resp.text,
                    "url": str(resp.request.url),
                    "status_code": resp.status_code,
                })
                parsed_json = None
        except ValueError as e:
            # Handle invalid JSON parsing
            logger.warning(
                "Failed to parse JSON",
                extra={
                    "url": str(resp.request.url),
                    "error": str(e),
                    "response_text": resp.text,
                },
            )
            # Manually replace single quotes with double quotes if needed (a common issue in malformed JSON responses)
            corrected_text = resp.text.replace("'", '"')  # This is just a workaround; it may not fix all cases
            logger.debug("Attempting to parse corrected response",
                         extra={"corrected_response_text": corrected_text[:500]})

            try:
                # Attempt parsing the corrected response
                parsed_json = httpx.Response.json(httpx.Response(content=corrected_text.encode()))
            except ValueError as parse_error:
                logger.warning("Failed to parse corrected JSON", extra={
                    "error": str(parse_error),
                    "corrected_response_text": corrected_text[:500],
                })
            text = resp.text

        # Log the raw response text if JSON parsing fails
        if text:
            logger.debug("Failed JSON response text", extra={"response_text": text[:500]})

        result = HttpGetResult(
            url=str(resp.request.url),
            status_code=resp.status_code,
            ok=200 <= resp.status_code < 300,
            json=parsed_json,
            text=text,
            elapsed_ms=elapsed_ms,
        )

        dumped = result.model_dump()

        # Log parsed response result before storing it
        logger.debug("Parsed response result", extra={
            "parsed_json": parsed_json,
            "response_body": dumped.get("body"),
            "elapsed_ms": elapsed_ms,
        })

        dumped["body"] = dumped.get("json") if dumped.get("json") is not None else dumped.get("text")

        context.execution_state[self.store_key] = dumped

        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[self.name] = dumped

        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)
