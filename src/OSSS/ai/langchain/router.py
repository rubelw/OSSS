from __future__ import annotations

from typing import Any, Dict

# whatever imports you already had…
# from langchain stuff ...

async def run_agent(
    *,
    message: str,
    session_id: str,
    agent_name: str = "lc.student_info_table",
) -> Dict[str, Any]:
    """
    Main LangChain entrypoint.

    - `agent_name` decides which LC agent/chain to use.
    - Returns at least {"reply": "..."} for router_agent.py.
    """
    # your existing logic that:
    # 1) looks up the LC agent by `agent_name`
    # 2) runs it
    # 3) returns {"reply": <string>, ...}
    ...
