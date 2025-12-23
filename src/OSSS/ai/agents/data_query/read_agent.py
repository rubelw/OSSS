# src/OSSS/ai/agents/data_query/read_agent.py
from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition


# ---------------------------------------------------------------------------
# Option B: define a small spec so _wrap_http_result is valid & reusable
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DataQuerySpec:
    name: str
    store_key: str
    source: str = "http"


class DataQueryAgent(BaseAgent):
    """
    HARD-WIRED: always GET /api/warrantys?skip=0&limit=100

    NOTE: If OSSS runs in Docker, "http://localhost:8000" points to the container.
    In that case, change BASE_URL to "http://host.containers.internal:8000"
    (Docker Desktop) or your compose service name.
    """
    name = "data_query"  # keep whatever your graph expects

    BASE_URL = "http://app:8000"
    PATH = "/api/warrantys"
    DEFAULT_PARAMS: Dict[str, Any] = {"skip": 0, "limit": 100}

    # This MUST match what your node wrapper is looking for: "data_query:<view>"
    VIEW_NAME = "warrantys"
    STORE_KEY = f"{name}:{VIEW_NAME}"  # "data_query:warrantys"

    def __init__(
        self,
        *,
        data_query: Dict[str, Any] | None = None,  # kept for compatibility, unused
        pg_engine: Optional[AsyncEngine] = None,    # kept for compatibility, unused
    ) -> None:
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_query = data_query or {}
        self.pg_engine = pg_engine

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(
            node_type="tool",
            agent_name=self.__class__.__name__,
            dependencies=[],
        )

    async def run(self, context: AgentContext) -> AgentContext:
        # Allow caller overrides, but default to skip=0&limit=100
        exec_cfg: Dict[str, Any] = context.execution_state.get("execution_config", {}) or {}
        params = dict(self.DEFAULT_PARAMS)
        params.update(exec_cfg.get("http_query_params", {}) or {})

        # ---- call backend_api_client ----
        from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig

        client = BackendAPIClient(BackendAPIConfig(base_url=self.BASE_URL))

        url = f"{self.BASE_URL.rstrip('/')}{self.PATH}"
        try:
            rows = await client.get_collection(
                self.VIEW_NAME,
                skip=int(params.get("skip", 0)),
                limit=int(params.get("limit", 100)),
                params={k: v for k, v in params.items() if k not in ("skip", "limit")},
            )
            payload: Dict[str, Any] = {
                "ok": True,
                "view": self.VIEW_NAME,
                "source": "http",
                "url": url,
                "status_code": 200,
                "row_count": len(rows),
                "rows": rows,
            }
        except Exception as e:
            payload = {
                "ok": False,
                "view": self.VIEW_NAME,
                "source": "http",
                "url": url,
                "status_code": None,
                "row_count": 0,
                "rows": [],
                "error": str(e),
            }

        # ------------------------------------------------------------------
        # ✅ CRITICAL: make the payload visible to LangGraph wrappers
        # ------------------------------------------------------------------

        # 1) Preferred: agent_outputs contains "data_query:<view>"
        context.add_agent_output(self.STORE_KEY, payload)

        # 2) Also set canonical "data_query" alias for older consumers
        #    (optional, but helpful for prompts / debugging)
        context.add_agent_output(self.name, payload)

        # 3) Wrapper fallback: execution_state["data_query_result"]
        context.execution_state["data_query_result"] = payload

        # 4) Keep your structured_outputs contract
        structured = context.execution_state.setdefault("structured_outputs", {})
        if isinstance(structured, dict):
            structured[self.STORE_KEY] = payload

        # 5) Keep the store_key payload as well (matches your existing behavior)
        context.execution_state[self.STORE_KEY] = payload

        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)

    # -----------------------------------------------------------------------
    # Safe helper for future expansion / reuse
    # -----------------------------------------------------------------------
    def _wrap_http_result(self, context: AgentContext, spec: DataQuerySpec) -> AgentContext:
        raw = context.execution_state.get(spec.store_key) or {}
        body = raw.get("json")

        rows: list[dict[str, Any]] = []
        if isinstance(body, list):
            rows = body
        elif isinstance(body, dict):
            for k in ("items", "data", "results"):
                v = body.get(k)
                if isinstance(v, list):
                    rows = v
                    break

        payload = {
            "ok": bool(raw.get("ok")),
            "view": spec.name,
            "source": spec.source,
            "url": raw.get("url"),
            "status_code": raw.get("status_code"),
            "row_count": len(rows),
            "rows": rows,
            "http": raw,
        }

        # Same visibility rules as run()
        context.add_agent_output(f"{self.name}:{spec.name}", payload)
        context.add_agent_output(self.name, payload)
        context.execution_state["data_query_result"] = payload

        context.execution_state[spec.store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        if isinstance(structured, dict):
            structured[f"{self.name}:{spec.name}"] = payload
        return context
