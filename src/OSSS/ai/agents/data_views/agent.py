from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.http_get.agent import HttpGetAgent
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class DataViewAgent(BaseAgent):
    """
    HARD-WIRED: always GET /api/warrantys?skip=0&limit=100

    NOTE: If OSSS runs in Docker, "http://localhost:8081" points to the container.
    In that case, change BASE_URL to "http://host.containers.internal:8081"
    (Docker Desktop) or your compose service name.
    """
    name = "data_views"  # keep whatever your graph expects

    # hard-wired target
    BASE_URL = "http://localhost:8000"
    PATH = "/api/warrantys"
    DEFAULT_PARAMS: Dict[str, Any] = {"skip": 0, "limit": 100}
    STORE_KEY = "data_view:warrantys"

    def __init__(
            self,
            *,
            data_views: Dict[str, Any] | None = None,  # kept for compatibility, unused
            pg_engine: Optional[AsyncEngine] = None,  # kept for compatibility, unused
    ) -> None:
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_views = data_views or {}
        self.pg_engine = pg_engine
        logger.debug("DataViewAgent initialized", extra={
            "data_views": self.data_views,
            "pg_engine": self.pg_engine
        })

    def get_node_definition(self) -> LangGraphNodeDefinition:
        logger.debug("Getting node definition", extra={"node_type": "tool", "agent_name": self.__class__.__name__})
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

        logger.debug("Running DataViewAgent with params", extra={
            "params": params,
            "execution_config": exec_cfg,
        })

        agent = HttpGetAgent(
            base_url=self.BASE_URL,
            path=self.PATH,
            timeout_s=10.0,
            query_params=params,
            store_key=self.STORE_KEY,
        )

        # Running the HttpGetAgent to fetch data
        logger.debug("Executing HTTP GET request via HttpGetAgent", extra={"base_url": self.BASE_URL, "path": self.PATH})
        context = await agent.run(context)

        # Log the data fetched by HttpGetAgent
        raw = context.execution_state.get(self.STORE_KEY) or {}
        logger.debug("Fetched raw data from HttpGetAgent", extra={"raw_data": raw})

        # Prepare the payload
        payload = {
            "ok": bool(raw.get("ok")),
            "view": "warrantys",
            "source": "http",
            "http": raw,
        }

        # Store the payload back in the execution state
        context.execution_state[self.STORE_KEY] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:warrantys"] = payload

        logger.debug("Processed and stored payload", extra={
            "payload": payload,
            "store_key": self.STORE_KEY
        })

        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        logger.debug("Invoking DataViewAgent", extra={"context": context})
        return await self.run(context)

    def _wrap_http_result(self, context: AgentContext, spec: DataViewSpec) -> AgentContext:
        raw = context.execution_state.get(spec.store_key) or {}
        body = raw.get("body")

        logger.debug("Wrapping HTTP result for DataView", extra={
            "store_key": spec.store_key,
            "body": body
        })

        rows: list[dict[str, Any]] = []
        if isinstance(body, list):
            rows = body
            logger.debug("Parsed body as list", extra={"rows": rows})
        elif isinstance(body, dict):
            # if the API ever returns a dict wrapper
            for k in ("items", "data", "results"):
                v = body.get(k)
                if isinstance(v, list):
                    rows = v
                    logger.debug(f"Found key '{k}' in body, parsing as list", extra={"rows": rows})
                    break

        payload = {
            "ok": bool(raw.get("ok")),
            "view": spec.name,
            "source": spec.source,
            "url": raw.get("url"),
            "status_code": raw.get("status_code"),
            "row_count": len(rows),
            "rows": rows,
            # keep the raw around for debugging
            "http": raw,
        }

        context.execution_state[spec.store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{spec.name}"] = payload

        logger.debug("Wrapped and stored HTTP result", extra={
            "payload": payload,
            "store_key": spec.store_key
        })

        return context
