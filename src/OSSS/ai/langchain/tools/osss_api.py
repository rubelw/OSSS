# src/OSSS/ai/langchain/tools/osss_api.py
from __future__ import annotations
from typing import Any, Dict, List
import os
import httpx

API_BASE = os.getenv("OSSS_API_BASE", "http://host.containers.internal:8081")


async def get_students(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(f"{API_BASE}/api/students", params={"skip": skip, "limit": limit})
        resp.raise_for_status()
        return resp.json()


async def get_persons(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(f"{API_BASE}/api/persons", params={"skip": skip, "limit": limit})
        resp.raise_for_status()
        return resp.json()
