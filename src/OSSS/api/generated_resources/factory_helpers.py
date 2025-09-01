# factory_helpers.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, get_args, get_origin
from uuid import UUID
from datetime import datetime, date
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

try:
    # Pydantic v2
    from pydantic import BaseModel, create_model
    V2 = True
except Exception:
    # Pydantic v1 fallback
    from pydantic import BaseModel, create_model
    V2 = False

_SQLA_TO_PY: Dict[type, Any] = {
    sa.String: str,
    sa.Text: str,
    sa.Integer: int,
    sa.BigInteger: int,
    sa.SmallInteger: int,
    sa.Boolean: bool,
    sa.Float: float,
    sa.Numeric: float,
    sa.DateTime: datetime,
    sa.Date: date,
    sa.Time: str,            # or datetime.time if you prefer
    sa.LargeBinary: bytes,
}

def _guess_field_type(col: sa.Column) -> Any:
    t = type(col.type)
    # UUID
    try:
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID
        if isinstance(col.type, PG_UUID):
            return UUID
    except Exception:
        pass

    # JSON / JSONB
    try:
        from sqlalchemy.dialects.postgresql import JSONB
        if isinstance(col.type, (sa.JSON, JSONB)):
            return dict | list | None  # v2 unions okay; v1 treat as 'dict' below
    except Exception:
        if isinstance(col.type, sa.JSON):
            return dict

    # ARRAY → list[Any]
    try:
        from sqlalchemy.dialects.postgresql import ARRAY
        if isinstance(col.type, ARRAY):
            return list
    except Exception:
        pass

    # Fallbacks from map
    for k, py in _SQLA_TO_PY.items():
        if isinstance(col.type, k):
            return py

    # If nothing matched, let it be 'Any'
    from typing import Any as _Any
    return _Any

def build_pydantic_from_sqla_model(sa_model: type) -> type[BaseModel]:
    insp = sa_inspect(sa_model)
    fields: Dict[str, Tuple[Any, Any]] = {}

    for col in insp.columns:
        py_type = _guess_field_type(col)
        default = None if col.nullable or col.default or col.server_default else ...
        # Pydantic v1 can't do unions like dict|list, so degrade JSON to dict
        if not V2 and (py_type == (dict | list | None)):
            py_type = dict
        fields[col.key] = (py_type, default)

    name = f"{sa_model.__name__}Out"
    model: type[BaseModel] = create_model(name, **fields)  # type: ignore[arg-type]
    if not V2:
        # Pydantic v1: enable orm_mode
        model.Config.orm_mode = True  # type: ignore[attr-defined]
    return model

def to_pydantic(obj: Any, Schema: type[BaseModel]) -> BaseModel | None:
    if obj is None:
        return None
    if V2:
        return Schema.model_validate(obj, from_attributes=True)  # pydantic v2
    else:
        return Schema.from_orm(obj)  # pydantic v1
