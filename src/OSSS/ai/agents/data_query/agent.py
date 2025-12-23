# src/OSSS/ai/agents/data_query/read_agent.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.http_get.agent import HttpGetAgent

import json

from typing import Any, Dict, List, Sequence, Optional

def _rows_to_markdown_table(
    rows: List[Dict[str, Any]],
    *,
    columns: Optional[Sequence[str]] = None,
    max_rows: int = 20,
) -> str:
    if not rows:
        return "_No rows returned._"

    # Choose columns
    if columns:
        cols = [c for c in columns if c]
    else:
        # union of keys in first N rows, stable-ish ordering
        cols_set = []
        seen = set()
        for r in rows[:max_rows]:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    cols_set.append(k)
        cols = cols_set or list(rows[0].keys())

    def esc(v: Any) -> str:
        if v is None:
            s = ""
        elif isinstance(v, (dict, list)):
            s = str(v)
        else:
            s = str(v)
        # markdown table hygiene
        s = s.replace("\n", " ").replace("|", "\\|")
        return s

    shown = rows[:max_rows]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = "\n".join("| " + " | ".join(esc(r.get(c, "")) for c in cols) + " |" for r in shown)

    more = ""
    if len(rows) > max_rows:
        more = f"\n\n_Showing {max_rows} of {len(rows)} rows._"

    return "\n".join([header, sep, body]) + more


def _as_content(payload: Dict[str, Any], *, max_rows: int = 20) -> str:
    """Make a prompt-safe text body while still keeping full payload in meta."""
    try:
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        trimmed = dict(payload)
        if isinstance(rows, list) and len(rows) > max_rows:
            trimmed["rows"] = rows[:max_rows]
            trimmed["rows_truncated"] = True
            trimmed["rows_total"] = len(rows)
        return json.dumps(trimmed, indent=2, default=str)
    except Exception:
        return str(payload)



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

    # hard-wired target
    BASE_URL = "http://app:8000"
    PATH = "/api/warrantys"
    DEFAULT_PARAMS: Dict[str, Any] = {"skip": 0, "limit": 100}
    STORE_KEY = "data_query:warrantys"
    VIEW_NAME = "warrantys"              # ✅ add this

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

        # ---- NEW: call backend_api_client instead of HttpGetAgent ----
        from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig

        client = BackendAPIClient(BackendAPIConfig(base_url=self.BASE_URL))

        try:
            rows = await client.get_collection(
                "warrantys",
                skip=int(params.get("skip", 0)),
                limit=int(params.get("limit", 100)),
                params={k: v for k, v in params.items() if k not in ("skip", "limit")},
            )
            payload = {
                "ok": True,
                "view": "warrantys",
                "source": "http",
                "url": f"{self.BASE_URL.rstrip('/')}{self.PATH}",
                "status_code": 200,
                "row_count": len(rows),
                "rows": rows,
            }
        except Exception as e:
            payload = {
                "ok": False,
                "view": "warrantys",
                "source": "http",
                "url": f"{self.BASE_URL.rstrip('/')}{self.PATH}",
                "status_code": None,
                "row_count": 0,
                "rows": [],
                "error": str(e),
            }

        # after payload is created (success or failure)

        context.execution_state[self.STORE_KEY] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:warrantys"] = payload

        # ✅ UI-friendly output
        if payload.get("ok"):
            md = _rows_to_markdown_table(
                payload.get("rows", []),
                max_rows=20,
                # optionally control columns:
                # columns=["asset_id", "vendor_id", "policy_no", "start_date", "end_date"],
            )
            context.add_agent_output(self.name, {
                "content": md,
                "meta": {
                    "view": payload.get("view"),
                    "row_count": payload.get("row_count"),
                    "url": payload.get("url"),
                    "status_code": payload.get("status_code"),
                },
                "action": "query",
                "intent": "action",
            })
        else:
            context.add_agent_output(self.name, {
                "content": f"**data_query failed**: {payload.get('error', 'unknown error')}",
                "meta": payload,
                "action": "query",
                "intent": "action",
            })

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
            # if the API ever returns a dict wrapper
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
            # keep the raw around for debugging
            "http": raw,
        }

        context.execution_state[spec.store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{spec.name}"] = payload
        return context
