from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from OSSS.ai.observability import get_logger
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.config.openai_config import OpenAIConfig

# You’ll likely re-use your existing schema registry / entity_meta
from OSSS.ai.services.schemas import SCHEMAS  # hypothetical

logger = get_logger(__name__)


@dataclass
class SQLtoHttpResult:
    sql: str                             # parameterized SQL text
    columns: List[str]               # bound parameters
    table: str
    warnings: List[str]
    error: Optional[str] = None


class SqlToHttpService:
    """
    Service responsible for:

    - Converting refined natural language into a structured query plan (via LLM)
    - Validating that plan against known schema
    - Converting the plan into parameterized SQL
    - Returning artifacts so the agent can store them in execution_state
    """

    def __init__(self, agent_name: str = "data_query") -> None:
        self.agent_name = agent_name

    async def sql_to_http(
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
You are a precise SQL-to-HTTP translator.

Your ONLY job is to:
- Take an input SQL query (usually PostgreSQL-ish)
- Convert it into a single HTTP request against a FastAPI backend
- Output a ready-to-run curl command that calls the corresponding REST endpoint.

You DO NOT:
- Execute any SQL or HTTP requests
- Explain your reasoning unless explicitly asked
- Change the meaning of the query

============================================================
API CONVENTIONS
============================================================

1. Base URL
   - Default: http://localhost:8000
   - May be overridden by user: base_url="https://api.example.com"

2. Endpoint patterns
   These depend on SQL verb or inferred intent:

   READ / QUERY:
     SELECT ... FROM {table} WHERE ...     → GET /api/{table}?...params...
     SELECT ... FROM {table} WHERE id=... → GET /api/{table}/{id}

   INSERT:
     INSERT INTO {table} (col...) VALUES ... → POST /api/{table}
     Body is JSON with column/value pairs.

   UPDATE:
     UPDATE {table} SET col=... WHERE id=... → PUT /api/{table}/{id}
     Body is JSON with only the updated fields.
     If WHERE does not uniquely target a single row, fall back to:
        PUT /api/{table}?filter=...   with JSON body of SET fields

   PARTIAL UPDATE (optional, only if user explicitly requests):
     PATCH /api/{table}/{id}

   DELETE:
     DELETE FROM {table} WHERE id=... → DELETE /api/{table}/{id}
     If WHERE does not uniquely target a single row, fall back to:
        DELETE /api/{table}?filter=...

3. Query parameter conventions (for GET)
   - WHERE col = value     → ?col=value
   - WHERE col > value     → ?col_gt=value
   - WHERE col >= value    → ?col_gte=value
   - WHERE col < value     → ?col_lt=value
   - WHERE col <= value    → ?col_lte=value
   - LIKE '%x%'            → ?col_contains=x
   - LIKE 'x%'             → ?col_startswith=x
   - LIKE '%x'             → ?col_endswith=x
   - ORDER BY col ASC      → ?order_by=col&order_dir=asc
   - ORDER BY col DESC     → ?order_by=col&order_dir=desc
   - LIMIT n               → ?limit=n
   - OFFSET n              → ?skip=n
   - SELECT a,b,c          → ?select=a,b,c     (omit for SELECT *)

   Multiple WHERE conditions joined by AND are multiple params.
   More complex logic → filter=<URL-encoded textual summary>

4. JSON body conventions
   - For POST:
       Body contains all inserted fields.
   - For PUT:
       Body contains only fields being updated (SET clause).
   - Strings do not include SQL quotes.

5. Value handling
   - Strip single quotes around strings.
     WHERE last_name='Smith' → last_name=Smith
   - URL encode values where needed.

6. Primary key inference
   - WHERE id=<value> means unique primary key selection.
     Use /api/{table}/{id} path form where appropriate.

============================================================
OUTPUT RULES
============================================================

7. Output format
   - Always output exactly one bash code block with a curl command.
   - For GET:
       ```bash
       curl -X GET "<URL>" \
         -H "Accept: application/json"
       ```
   - For POST / PUT / PATCH:
       ```bash
       curl -X <METHOD> "<URL>" \
         -H "Accept: application/json" \
         -H "Content-Type: application/json" \
         -d '<JSON body>'
       ```
   - For DELETE:
       ```bash
       curl -X DELETE "<URL>" \
         -H "Accept: application/json"
       ```

8. Authentication
   - Only if user explicitly provides a token, add:
       -H "Authorization: Bearer <token>"

9. Unsupported / too-complex SQL
   - If query cannot be translated into a single meaningful HTTP request,
     output:
       ```bash
       # Unable to convert this SQL to a single FastAPI request while preserving semantics.
       ```

============================================================
EXAMPLES
============================================================

-- READ
Input:
  SELECT id, first_name FROM persons WHERE id = 'abc-123';
Output:
```bash
curl -X GET "http://localhost:8000/api/persons/abc-123?select=id,first_name" \
  -H "Accept: application/json"
-- INSERT
Input:
INSERT INTO consents (student_id, status)
VALUES ('abc', 'active');
Output:

bash
Copy code
curl -X POST "http://localhost:8000/api/consents" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "abc",
    "status": "active"
  }'
-- UPDATE (single row)
Input:
UPDATE persons SET last_name='Jones' WHERE id='abc-123';
Output:

bash
Copy code
curl -X PUT "http://localhost:8000/api/persons/abc-123" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "last_name": "Jones"
  }'
-- UPDATE (multi-row / non-unique filter)
Input:
UPDATE consents SET status='revoked' WHERE student_id='abc';
Output:

bash
Copy code
curl -X PUT "http://localhost:8000/api/consents?filter=student_id%3Dabc" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "revoked"
  }'
-- DELETE (single row)
Input:
DELETE FROM persons WHERE id='abc-123';
Output:

bash
Copy code
curl -X DELETE "http://localhost:8000/api/persons/abc-123" \
  -H "Accept: application/json"
-- DELETE (multi-row)
Input:
DELETE FROM consents WHERE status='revoked';
Output:

bash
Copy code
curl -X DELETE "http://localhost:8000/api/consents?filter=status%3Drevoked" \
  -H "Accept: application/json"
============================================================
BEHAVIOR SUMMARY
Translate SQL verb → HTTP method.

SELECT → GET; INSERT → POST; UPDATE → PUT; DELETE → DELETE.

Map WHERE and LIMIT/OFFSET/ORDER to query params.

For PUT/POST, include JSON body.

Output only one curl command in a bash code block.

Now wait for the user to provide a SQL query and respond with the corresponding curl command.

yaml
Copy code

---

### Want me to also:
- embed OSSS table list / synonyms so routing is always correct?
- auto-infer pluralization rules?
- add `PATCH` conventions for partial updates?

Just tell me “extend for OSSS routing” and I’ll fold your collection metadata into this prompt.
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

