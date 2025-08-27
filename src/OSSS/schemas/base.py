from __future__ import annotations
from typing import Any, Union
from pydantic import BaseModel, ConfigDict, RootModel

ID = Union[int, str]

class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class FreeObject(RootModel[dict[str, Any]]):
    root: dict[str, Any]
