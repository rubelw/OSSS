from __future__ import annotations

from typing import Any
from pydantic import Field
from .base import APIModel, FreeObject, ID


class QueryParams(APIModel):
    skip: int = Field(0, ge=0, description="Items to skip")
    limit: int = Field(100, ge=1, le=1000, description="Max items to return")


class ReadOne(APIModel):
    data: dict[str, Any]


class ReadMany(APIModel):
    items: list[dict[str, Any]]
    total: int | None = None
    skip: int = 0
    limit: int = 100


class DeleteResponse(APIModel):
    deleted: bool = True
    id: ID | None = None


class CreatePayload(FreeObject):
    ...


class ReplacePayload(FreeObject):
    ...


class PatchPayload(FreeObject):
    ...
