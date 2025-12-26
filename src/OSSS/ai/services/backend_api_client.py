# src/OSSS/ai/services/backend_api_client.py
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import httpx
from pydantic import BaseModel


class BackendAPIConfig(BaseModel):
    """
    Simple config object for the backend API client.

    Example:
        BackendAPIConfig(base_url="http://app:8000")
    """
    base_url: str
    timeout_seconds: float = 30.0


class BackendAPIClient:
    """
    Generic FastAPI-backed client.

    Assumes endpoints like:
      GET {base_url}/api/<collection>?skip=0&limit=100

    `get_collection` expects a JSON array (list[dict]).
    `get_detail` is more flexible and will return whatever JSON shape the API
    provides (dict, list, primitive, etc.).
    """

    def __init__(self, config: BackendAPIConfig) -> None:
        self.config = config
        # Persistent AsyncClient with base_url and default timeout
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url.rstrip("/"),
            timeout=self.config.timeout_seconds,
        )

    async def aclose(self) -> None:
        """
        Explicitly close the underlying HTTP client.

        Call this from your app shutdown hook if you want clean teardown.
        """
        await self._client.aclose()

    # 👇 NEW: generic JSON helper for arbitrary paths
    async def get_json(
        self,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """
        Convenience wrapper to GET JSON from the backend.

        `path` can be:
        - relative (e.g. "/api/consents")
        - or a full URL (e.g. "http://localhost:8000/api/consents")

        Returns: whatever JSON the backend returns.
        """
        normalized = path  # httpx.AsyncClient supports absolute or relative paths

        merged_headers: Dict[str, str] = {"accept": "application/json"}
        if headers:
            merged_headers.update(dict(headers))

        resp = await self._client.get(
            normalized,
            params=dict(params or {}),
            headers=merged_headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_collection(
        self,
        collection: str,
        *,
        skip: int = 0,
        limit: int = 100,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> list[dict]:
        """
        Fetch a collection from the backend API.

        - collection: e.g. "warrantys"
        - skip/limit: standard pagination
        - params: extra query string parameters (merged with skip/limit)
        - headers: optional headers (merged with Accept: application/json)

        Returns: list[dict]
        """
        collection = (collection or "").strip().strip("/")
        if not collection:
            raise ValueError("collection must be a non-empty string")

        # Build relative path; base_url is handled by the AsyncClient
        path = f"/api/{collection}"

        # Merge params with skip/limit (skip/limit win)
        merged_params: Dict[str, Any] = dict(params or {})
        merged_params["skip"] = skip
        merged_params["limit"] = limit

        # Default headers; allow per-call overrides
        merged_headers: Dict[str, str] = {"accept": "application/json"}
        if headers:
            merged_headers.update(dict(headers))

        data = await self.get_json(
            path,
            params=merged_params,
            headers=merged_headers,
        )

        if not isinstance(data, list):
            raise ValueError(
                f"Expected list response from GET {path}, got {type(data)}: {data!r}"
            )

        # Ensure each item is a dict-ish JSON object
        out: list[dict] = []
        for item in data:
            if isinstance(item, dict):
                out.append(item)
            else:
                # keep it defensive; you can also choose to raise instead
                out.append({"value": item})
        return out

    # Generic detail helper for arbitrary paths
    async def get_detail(
        self,
        *,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """
        Fetch a single resource at the given path, e.g. "/api/warrantys/{id}".

        `path` can be absolute or relative; we normalize a leading '/'.

        Returns: whatever JSON the backend returns (dict, list, primitive, etc.).
        """
        # Normalize relative vs absolute
        normalized = path if path.startswith("/") else f"/{path}"

        merged_headers: Dict[str, str] = {"accept": "application/json"}
        if headers:
            merged_headers.update(dict(headers))

        resp = await self._client.get(
            normalized,
            params=dict(params or {}),
            headers=merged_headers,
        )
        resp.raise_for_status()
        return resp.json()
