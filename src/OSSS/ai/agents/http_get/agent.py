# src/OSSS/ai/agents/http/http_get_agent.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import httpx

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from .models import HttpGetResult


class HttpGetAgent(BaseAgent):
    """
    Agent that performs an HTTP GET against a FastAPI endpoint and stores results in context.

    Typical uses:
    - fetch reference data before other agents
    - pull tools/results from internal services
    - enrich query context with structured payloads
    """

    # Keep this consistent with how your system keys agents (often lowercase)
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
        # ✅ Align with the rest of your agents (BaseAgent init + timeout wiring)
        super().__init__(name=self.name, timeout_seconds=timeout_s)

        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"
        self.timeout_s = timeout_s
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.store_key = store_key
        self.auth_token_env = auth_token_env

    # Keep this if your GraphBuilder uses LangGraphNodeDefinition
    def get_node_definition(self) -> LangGraphNodeDefinition:
        """
        Node definition used by GraphBuilder / orchestrator.
        Adjust fields to match your LangGraphNodeDefinition shape.
        """
        return LangGraphNodeDefinition(
            node_type="tool",        # or "processor" depending on your taxonomy
            agent_name="HttpGetAgent",
            dependencies=[],         # set if it must run after another agent
        )

    # ✅ Align with the rest of your agents: entrypoint is run()
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Execute GET request and attach results to context.execution_state.
        """
        exec_cfg: Dict[str, Any] = (
            context.execution_state.get("execution_config", {}) or {}
        )
        headers = dict(self.headers)

        # Optional bearer token from env name
        if self.auth_token_env:
            token = os.getenv(self.auth_token_env)
            if token:
                headers.setdefault("Authorization", f"Bearer {token}")

        # Allow query params to be augmented dynamically
        params = dict(self.query_params)
        params.update(exec_cfg.get("http_query_params", {}))

        url = f"{self.base_url}{self.path}"

        start = time.time()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.get(url, params=params, headers=headers)
        elapsed_ms = int((time.time() - start) * 1000)

        # Parse JSON if possible; otherwise keep text
        parsed_json = None
        text = None
        try:
            parsed_json = resp.json()
        except Exception:
            text = resp.text

        result = HttpGetResult(
            url=str(resp.request.url),
            status_code=resp.status_code,
            ok=200 <= resp.status_code < 300,
            json=parsed_json,
            text=text,
            elapsed_ms=elapsed_ms,
        )

        # Store for downstream agents
        context.execution_state[self.store_key] = result.model_dump()

        # Also publish under the common structured_outputs convention
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[self.name] = result.model_dump()

        return context

    # ✅ Backward compatibility if anything still calls invoke()
    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)
