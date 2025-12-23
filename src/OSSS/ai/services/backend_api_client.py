from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional
import httpx


@dataclass(frozen=True)
class BackendAPIConfig:
    base_url: str  # e.g. "http://localhost:8000"


class BackendAPIClient:
    """
    Generic FastAPI-backed collection fetcher.

    Assumes endpoints like:
      GET {base_url}/api/<collection>?skip=0&limit=100
    returning JSON arrays (list[dict]).
    """

    def __init__(self, config: BackendAPIConfig) -> None:
        self._config = config

    def _url_for_collection(self, collection: str) -> str:
        collection = (collection or "").strip().strip("/")
        if not collection:
            raise ValueError("collection must be a non-empty string")
        return f"{self._config.base_url.rstrip('/')}/api/{collection}"

    async def get_collection(
        self,
        collection: str,
        *,
        skip: int = 0,
        limit: int = 100,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 30.0,
    ) -> list[dict]:
        """
        Fetch a collection from the backend API.

        - collection: e.g. "warrantys"
        - skip/limit: standard pagination
        - params: extra query string parameters (merged with skip/limit)
        - headers: optional headers (merged with accept: application/json)

        Returns: list[dict]
        """
        url = self._url_for_collection(collection)

        # Merge params with skip/limit (skip/limit win)
        merged_params: dict[str, Any] = dict(params or {})
        merged_params["skip"] = skip
        merged_params["limit"] = limit

        merged_headers: dict[str, str] = {"accept": "application/json"}
        if headers:
            merged_headers.update(dict(headers))

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.get(url, params=merged_params, headers=merged_headers)
            resp.raise_for_status()

            data = resp.json()
            if not isinstance(data, list):
                raise ValueError(
                    f"Expected list response from GET {url}, got {type(data)}: {data!r}"
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
