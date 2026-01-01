from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from OSSS.ai.observability import get_logger
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.services.schemas import SCHEMAS  # your schema registry

logger = get_logger(__name__)


@dataclass
class NLToSQLResult:
    plan: Dict[str, Any]
    sql: str
    params: Dict[str, Any]
    table: str
    warnings: List[str]
    error: Optional[str] = None


class NLToSQLService:
    """
    Service responsible for:

    - Converting refined natural language into a structured query plan (via LLM)
    - Validating that plan against known schema
    - Converting the plan into parameterized SQL
    - Returning artifacts so the agent can store them in execution_state
    """

    def __init__(self, agent_name: str = "data_query") -> None:
        self.agent_name = agent_name

    # ---------------------------------------------------------
    # Table / column introspection helpers
    # ---------------------------------------------------------

    @staticmethod
    def list_tables() -> List[str]:
        """
        Return a sorted list of all table names known in SCHEMAS.
        """
        try:
            tables = sorted(SCHEMAS.keys())
            logger.debug(
                "NLToSQLService.list_tables",
                extra={
                    "event": "nl_to_sql_list_tables",
                    "table_count": len(tables),
                    "tables_preview": tables[:10],
                },
            )
            return tables
        except Exception as exc:
            logger.error(
                "Failed to list tables from SCHEMAS",
                exc_info=True,
                extra={"error_type": type(exc).__name__},
            )
            return []

    @staticmethod
    def list_fields(table_name: str) -> List[str]:
        """
        List all columns defined for a given table inside SCHEMAS.

        Returns an empty list if the table is unknown or malformed.
        """
        try:
            schema = SCHEMAS.get(table_name)
            if not schema:
                logger.warning(
                    "Unknown table in NLToSQLService.list_fields",
                    extra={"table": table_name},
                )
                return []

            cols = list(schema.get("columns", {}).keys())
            logger.debug(
                "NLToSQLService.list_fields",
                extra={
                    "event": "nl_to_sql_list_fields",
                    "table": table_name,
                    "field_count": len(cols),
                    "fields_preview": cols[:10],
                },
            )
            return cols

        except Exception as exc:
            logger.error(
                "Failed to list fields for table",
                exc_info=True,
                extra={"table": table_name, "error_type": type(exc).__name__},
            )
            return []

    @staticmethod
    def list_foreign_key_fields(
        table_name: str,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Return a mapping of FK columns for a given table:

            {
                "school_id": {"table": "schools", "field": "id"},
                "student_id": {"table": "students", "field": "id"},
                ...
            }

        Expects FK metadata to be stored on the column config, e.g.:

            "columns": {
                "school_id": {
                    "type": "uuid",
                    "foreign_key_table": "schools",
                    "foreign_key_field": "id",
                },
                ...
            }

        Falls back to 'ref_table' / 'ref_column' if those keys are used.
        """
        try:
            schema = SCHEMAS.get(table_name)
            if not schema:
                logger.warning(
                    "Unknown table in NLToSQLService.list_foreign_key_fields",
                    extra={"table": table_name},
                )
                return {}

            cols: Dict[str, Any] = schema.get("columns", {}) or {}
            fk_map: Dict[str, Dict[str, Optional[str]]] = {}

            for col_name, col_meta in cols.items():
                # If the column is just a type string, there is no FK info.
                if not isinstance(col_meta, dict):
                    continue

                # Support both your wizard-style names and a more generic one.
                fk_table = (
                    col_meta.get("foreign_key_table")
                    or col_meta.get("ref_table")
                )
                fk_field = (
                    col_meta.get("foreign_key_field")
                    or col_meta.get("ref_column")
                )

                if fk_table and fk_field:
                    fk_map[col_name] = {
                        "table": fk_table,
                        "field": fk_field,
                    }

            logger.debug(
                "NLToSQLService.list_foreign_key_fields",
                extra={
                    "event": "nl_to_sql_list_fk_fields",
                    "table": table_name,
                    "fk_count": len(fk_map),
                    "fk_preview": {
                        k: v for i, (k, v) in enumerate(fk_map.items()) if i < 5
                    },
                },
            )
            return fk_map

        except Exception as exc:
            logger.error(
                "Failed to list foreign key fields for table",
                exc_info=True,
                extra={"table": table_name, "error_type": type(exc).__name__},
            )
            return {}

    # ---------------------------------------------------------
    # LLM → plan → SQL (unchanged)
    # ---------------------------------------------------------

    async def nl_to_plan(
        self,
        *,
        refined_query: str,
        table_name: str,
    ) -> Dict[str, Any]:
        """
        Call LLM to get a JSON query plan (no SQL).
        """
        schema = SCHEMAS.get(table_name)
        if not schema:
            raise ValueError(f"Unknown table {table_name!r} in NLToSQLService.nl_to_plan")

        columns = ", ".join(schema["columns"].keys())

        system_prompt = f"""
You are a query planner for a PostgreSQL database.

Table: {table_name}
Columns: {columns}

Goal: Convert the user request into a JSON query plan.
Do NOT write SQL. Only return JSON with:

- operation: "read" | "create" | "update" | "delete"
- table: string
- columns: list of column names to select (use only from Columns above)
- filters: list of objects:
    {{ "column": <name>, "op": "=", "value": <value> }}
- order_by: list of objects:
    {{ "column": <name>, "direction": "asc" | "desc" }}
- limit: integer

Rules:
- Use only known columns.
- If user doesn't specify columns, use a reasonable default.
- If no limit mentioned, use 100.
- Return ONLY a JSON object, nothing else.
        """.strip()

        user_prompt = f"User request:\n{refined_query}"

        llm_config = OpenAIConfig.load()
        llm = OpenAIChatLLM(
            api_key=llm_config.api_key,
            model=llm_config.model,
            base_url=llm_config.base_url,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        resp = await llm.ainvoke(messages)

        import json
        plan = json.loads(resp.text)
        plan.setdefault("table", table_name)
        return plan

    def plan_to_sql(
        self,
        plan: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Deterministically convert a validated plan into SQL + params.
        """
        warnings: List[str] = []
        table = plan["table"]
        schema = SCHEMAS[table]

        cols = plan.get("columns") or schema.get("default_select") or ["*"]
        validated_cols = []
        for c in cols:
            if c == "*":
                validated_cols = ["*"]
                break
            if c not in schema["columns"]:
                warnings.append(f"Unknown column {c!r}; dropping from select")
                continue
            validated_cols.append(c)

        if not validated_cols:
            validated_cols = schema.get("default_select") or ["*"]

        select_clause = ", ".join(validated_cols)
        sql = f"SELECT {select_clause} FROM {table}"
        params: Dict[str, Any] = {}

        # WHERE
        filters = plan.get("filters") or []
        where_parts = []
        allowed_ops = {"=", ">", "<", ">=", "<=", "<>", "!="}
        for i, flt in enumerate(filters):
            col = flt.get("column")
            op = flt.get("op", "=")
            if col not in schema["columns"]:
                warnings.append(f"Unknown filter column {col!r}; dropping filter")
                continue
            if op not in allowed_ops:
                warnings.append(f"Unsupported operator {op!r}; dropping filter")
                continue
            pname = f"p{i}"
            where_parts.append(f"{col} {op} :{pname}")
            params[pname] = flt.get("value")

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        # ORDER BY
        order_by = plan.get("order_by") or []
        if order_by:
            parts = []
            for ob in order_by:
                col = ob.get("column")
                direction = (ob.get("direction") or "asc").lower()
                if col not in schema["columns"]:
                    warnings.append(f"Unknown order_by column {col!r}; dropping")
                    continue
                if direction not in {"asc", "desc"}:
                    warnings.append(
                        f"Invalid order direction {direction!r}; defaulting to asc"
                    )
                    direction = "asc"
                parts.append(f"{col} {direction.upper()}")
            if parts:
                sql += " ORDER BY " + ", ".join(parts)

        # LIMIT
        default_limit = schema.get("default_limit", 100)
        limit = plan.get("limit") or default_limit
        sql += " LIMIT :limit"
        params["limit"] = int(limit)

        return sql, params, warnings

    async def build_sql_from_nl(
        self,
        *,
        refined_query: str,
        table_name: str,
    ) -> NLToSQLResult:
        """
        Full pipeline: NL -> plan (LLM) -> SQL (deterministic).
        """
        try:
            plan = await self.nl_to_plan(
                refined_query=refined_query,
                table_name=table_name,
            )
            sql, params, warnings = self.plan_to_sql(plan)
            return NLToSQLResult(
                plan=plan,
                sql=sql,
                params=params,
                table=table_name,
                warnings=warnings,
            )
        except Exception as exc:
            logger.error(
                "NLToSQLService.build_sql_from_nl failed",
                exc_info=True,
                extra={"error_type": type(exc).__name__},
            )
            return NLToSQLResult(
                plan={},
                sql="",
                params={},
                table=table_name,
                warnings=[],
                error=str(exc),
            )
