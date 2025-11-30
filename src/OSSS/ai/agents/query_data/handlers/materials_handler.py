# OSSS/ai/agents/query_data/handlers/materials_handler.py
from __future__ import annotations

from typing import Any, Dict, List
import csv
import io
import logging

import httpx

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    FetchResult,
    QueryHandler,
    register_handler,
)

logger = logging.getLogger("OSSS.ai.agents.query_data.materials")


API_BASE = "http://host.containers.internal:8081"


class MaterialsHandler:
    """
    QueryData handler for the /api/materials endpoint.

    Example row shape (from your FastAPI service):

    {
        "type": "LINK",
        "title": "Sample materials title",
        "url": "Sample materials url",
        "drive_file_id": "f0a9dd7e-ab6f-5136-82b7-9545154a353e",
        "payload": "Sample materials payload",
        "announcement_id": "94a31cc3-022a-560d-9d1b-e68435d18c55",
        "coursework_id": "a0bcb2ea-b232-566d-afd7-787154b091e3",
        "id": "f6f6a4c5-8476-56ea-aefb-cf16852524cc",
        "created_at": "2025-09-05T18:25:42+00:00",
        "updated_at": "2025-09-05T18:25:42+00:00"
    }
    """

    # Required by QueryHandler protocol
    mode: str = "materials"
    keywords: List[str] = [
        "materials",
        "materials list",
        "material list",
        "supply list",
        "supplies list",
    ]
    source_label: str = "your DCG OSSS materials service"

    # ------------------------------------------------------------------ #
    # Data fetch
    # ------------------------------------------------------------------ #
    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:
        url = f"{API_BASE}/api/materials"
        params = {"skip": skip, "limit": limit}

        logger.info("MaterialsHandler.fetch url=%s params=%s", url, params)

        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            materials: List[Dict[str, Any]] = resp.json()

        logger.info("MaterialsHandler.fetch got %d rows", len(materials))

        # `rows` is what QueryDataAgent expects; the rest is just debug info.
        return {
            "rows": materials,
            "materials": materials,
            "materials_url": url,
        }

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        """Return materials list as a markdown table."""
        if not rows:
            return "No materials were found in the system."

        header = (
            "| # | Type | Title | URL | Drive File ID | Announcement ID | "
            "Coursework ID | Payload | Material ID | Created At | Updated At |\n"
            "|---|------|-------|-----|--------------|-----------------|"
            "--------------|---------|------------|------------|------------|\n"
        )

        lines: List[str] = []
        for idx, r in enumerate(rows, start=1):
            lines.append(
                f"| {idx} | "
                f"{r.get('type', '')} | "
                f"{r.get('title', '')} | "
                f"{r.get('url', '')} | "
                f"{r.get('drive_file_id', '')} | "
                f"{r.get('announcement_id', '')} | "
                f"{r.get('coursework_id', '')} | "
                f"{(r.get('payload', '') or '')[:80]} | "  # truncate payload for table
                f"{r.get('id', '')} | "
                f"{r.get('created_at', '')} | "
                f"{r.get('updated_at', '')} |"
            )

        return header + "\n".join(lines)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        """Return materials list as CSV."""
        if not rows:
            return ""

        output = io.StringIO()
        fieldnames = [
            "type",
            "title",
            "url",
            "drive_file_id",
            "payload",
            "announcement_id",
            "coursework_id",
            "id",
            "created_at",
            "updated_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in fieldnames})

        return output.getvalue()


# Register on import so QueryDataAgent can discover it.
register_handler(MaterialsHandler())
