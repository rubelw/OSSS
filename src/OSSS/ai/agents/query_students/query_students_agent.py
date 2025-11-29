from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

logger = logging.getLogger("OSSS.ai.agents.query_students.agent")


# You can later move this into OSSS.config.settings if you want.
# For now, default to host.containers.internal so it can hit your host's port 8081.
API_BASE = "http://host.containers.internal:8081"
# If you really want tutor-api once networking is right:
# API_BASE = "http://tutor-api:8081"


@register_agent("query_students")
class QueryStudentsAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        url = f"{API_BASE}/api/students"
        params = {"skip": 0, "limit": 100}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                students: List[Dict[str, Any]] = resp.json()
        except Exception as e:
            logger.exception("Error calling students API")

            # IMPORTANT: construct AgentResult with answer_text + data
            answer_text = (
                "I tried to query the students service, but there was a "
                "network error reaching it. Please verify the students API "
                f"is running and accessible at {url}."
            )

            return AgentResult(
                answer_text=answer_text,
                status="error",
                intent="query_students",
                agent_id="query_students",
                agent_name="QueryStudentsAgent",
                data={
                    "error": str(e),
                    "url": url,
                    "agent_debug_information": {
                        "phase": "query_students_error",
                        "query": ctx.query,
                    },
                },
            )

        count = len(students)
        if count == 0:
            answer_text = (
                "I queried the students service, but it did not return any students."
            )
        else:
            sample = students[:5]
            answer_text = (
                f"I found {count} students from the students API. "
                f"Here are the first {len(sample)} entries:\n\n"
            )
            for idx, s in enumerate(sample, start=1):
                name = (
                    s.get("name")
                    or s.get("full_name")
                    or s.get("student_name")
                    or "Unknown"
                )
                sid = s.get("id") or s.get("student_id")
                grade = s.get("grade_level") or s.get("grade")

                line = f"- {idx}. {name}"
                if grade is not None:
                    line += f" (grade {grade})"
                if sid is not None:
                    line += f" [id: {sid}]"
                answer_text += line + "\n"

        return AgentResult(
            answer_text=answer_text,
            status="ok",
            intent="query_students",
            agent_id="query_students",
            agent_name="QueryStudentsAgent",
            data={
                "students": students,
                "count": count,
                "agent_debug_information": {
                    "phase": "query_students",
                    "query": ctx.query,
                    "returned_count": count,
                },
            },
        )
