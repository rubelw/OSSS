# src/OSSS/ai/langchain_agent.py
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
# If you want to use Ollama directly via LangChain instead of OpenAI:
# from langchain_ollama import ChatOllama

logger = logging.getLogger("OSSS.ai.langchain_agent")

DEFAULT_MODEL = os.getenv("OSSS_LANGCHAIN_MODEL", "llama3.2-vision")
API_BASE = os.getenv("OSSS_API_BASE", "http://host.containers.internal:8081")


SYSTEM_PROMPT = """You are the OSSS LangChain agent.

- For general questions, respond clearly and concisely.
- When asked to "show student info", "show students", "list students",
  or similar, you SHOULD rely on the live-data pipeline if available.
- Prefer tabular markdown output when returning records (| col1 | col2 | ... |).

If you are not given any live data, do NOT invent exact names, IDs, or counts.
"""


def get_llm(model: Optional[str] = None) -> BaseChatModel:
    """
    Construct a LangChain chat model.

    Right now this uses langchain-openai's ChatOpenAI pointed at whatever
    OSSS_LANGCHAIN_MODEL / OPENAI_API_KEY (or compatible) you have configured.

    If you want to use Ollama instead, swap this out for ChatOllama.
    """
    model_name = (model or DEFAULT_MODEL).strip()

    # Example using OpenAI-compatible chat model
    return ChatOpenAI(
        model=model_name,
        temperature=0.1,
        max_tokens=2048,
    )

    # If you want to use Ollama via LangChain instead, comment out the block
    # above and uncomment something like:
    #
    # return ChatOllama(
    #     model=model_name,
    #     temperature=0.1,
    # )


# ---------------------------------------------------------------------------
# Live-data helpers for students
# ---------------------------------------------------------------------------

async def _fetch_students_and_persons(*, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch a small sample of students + their person records from the OSSS API
    and return joined rows suitable for display in a table.

    This mirrors the behavior of your query_data.students_handler, but is
    implemented locally so the LangChain agent can use it directly.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Adjust skip/limit as needed; we just want a demo slice
        students_resp = await client.get(
            f"{API_BASE}/api/students",
            params={"skip": 0, "limit": limit},
        )
        students_resp.raise_for_status()
        students = students_resp.json()

        persons_resp = await client.get(
            f"{API_BASE}/api/persons",
            params={"skip": 0, "limit": limit},
        )
        persons_resp.raise_for_status()
        persons = persons_resp.json()

    persons_by_id = {p["id"]: p for p in persons}

    combined_rows: List[Dict[str, Any]] = []
    for s in students:
        p = persons_by_id.get(s.get("person_id"))
        if not p:
            continue

        combined_rows.append(
            {
                "First": p.get("first_name"),
                "Middle": p.get("middle_name"),
                "Last": p.get("last_name"),
                "DOB": p.get("dob"),
                "Email": p.get("email"),
                "Phone": p.get("phone"),
                "Gender": p.get("gender"),
                "Person ID": p.get("id"),
                "Created At": p.get("created_at"),
                "Updated At": p.get("updated_at"),
                "Student ID": s.get("id"),
                "Student Number": s.get("student_number"),
                "Graduation Year": s.get("graduation_year"),
            }
        )

    return combined_rows


def _rows_to_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """
    Convert list-of-dicts rows into a markdown table.
    """
    if not rows:
        return "No student records were found."

    # Use the keys from the first row as column order
    headers = list(rows[0].keys())
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "|" + "|".join(["---"] * len(headers)) + "|"

    lines = [header_line, separator_line]
    for row in rows:
        cells = [str(row.get(h, "")) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


async def _handle_student_info_query(message: str) -> str:
    """
    Specialized path for queries like "show student info".
    This bypasses the generic LLM answer and hits the OSSS API instead.
    """
    try:
        rows = await _fetch_students_and_persons(limit=5)
        table_md = _rows_to_markdown_table(rows)

        return (
            "Here is a sample of student records from your OSSS demo database:\n\n"
            f"{table_md}\n\n"
            "---\n"
            "This data is coming from the live OSSS `/api/students` and `/api/persons` "
            "endpoints via the LangChain agent."
        )
    except Exception as e:
        # Log the error and fall back to a safe message instead of crashing.
        logger.exception("LangChain student_info live-data path failed: %s", e)
        return (
            "I tried to fetch live student records from the OSSS API, but ran into an error. "
            "Please check that the OSSS backend is running and reachable from the LangChain agent."
        )


# ---------------------------------------------------------------------------
# Public entry point used by RouterAgent
# ---------------------------------------------------------------------------

async def run_agent(
    message: str,
    session_id: Optional[str] = None,
    *,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point for the LangChain agent.

    - For "student info"–style queries, call the OSSS API and return a real
      table of demo students.
    - For everything else, fall back to a simple chat-completion call guided
      by SYSTEM_PROMPT.

    The RouterAgent treats the returned dict as:
      {"reply": "<text to send back to the user>"}.
    """
    msg_l = (message or "").lower().strip()

    # 🚧 Heuristic: treat "student_info" style phrases as a signal to hit live data.
    if (
        "show student info" in msg_l
        or "show students" in msg_l
        or msg_l.startswith("students ")
        or msg_l.startswith("student ")
    ):
        reply_text = await _handle_student_info_query(message)
        return {"reply": reply_text}

    # -------------------- generic LLM fallback --------------------
    llm = get_llm(model=model)

    msgs = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ]

    resp = await llm.ainvoke(msgs)

    # langchain_openai ChatOpenAI returns a ChatMessage-like object
    reply_text = getattr(resp, "content", str(resp))

    return {"reply": reply_text}
