from __future__ import annotations
from typing import Any, Union
from pydantic import BaseModel, ConfigDict, RootModel

ID = Union[int, str]


class APIModel(BaseModel):
    # Pydantic v2 config (replacement for `class Config: orm_mode = True`)
    model_config = ConfigDict(
        from_attributes=True,   # replaces orm_mode = True
        extra="ignore",         # same as Config.extra = "ignore"
        populate_by_name=True,  # replaces allow_population_by_field_name = True
        # use_enum_values=True,   # uncomment if you previously had Config.use_enum_values = True
        # json_schema_extra={...},# carry over if you had it
    )


class FreeObject(RootModel[dict[str, Any]]):
    root: dict[str, Any]
