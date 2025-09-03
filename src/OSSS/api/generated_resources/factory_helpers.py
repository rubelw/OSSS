# factory_helpers.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, get_args, get_origin, Type
from uuid import UUID
from datetime import datetime, date
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
import re

__all__ = ["resource_name_for_model"]

_ACRONYM_BOUNDARY = re.compile(r'([A-Z]+)([A-Z][a-z])')  # CIC + A -> CIC_A
_MIDWORD_BOUNDARY = re.compile(r'([a-z0-9])([A-Z])')     # fooB -> foo_B


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

def _camel_to_snake_acronym_aware(name: str) -> str:
    """Turn CamelCase (incl. ALLCAPS acronyms) into snake_case.
    CICMeeting -> cic_meeting, HTTPServerError -> http_server_error
    """
    # split between ALLCAPS + Capitalized (…CIC|Meeting -> CIC_Meeting)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    # split between lowercase/digit and Capital (…c|M -> c_M)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()

def resource_name_for_model(model: Type) -> str:
    """
    Return the canonical resource name for a model.

    Priority:
      1) model.__tablename__ (preferred, already plural and stable)
      2) model.__table__.name if present
      3) CamelCase -> snake_case with acronym handling, then naive pluralize.
    """
    # 1) Prefer SQLAlchemy table name (already correct for CICMeeting -> "cic_meetings")
    tn = getattr(model, "__tablename__", None)
    if tn:
        return tn

    table = getattr(model, "__table__", None)
    if table is not None and getattr(table, "name", None):
        return table.name

    # 2) Fallback: derive from class name, but collapse acronyms
    # "CICMeeting" -> "cic_meeting" -> "cic_meetings"
    name = model.__name__

    # collapse runs of capitals before Capital-lowercase boundaries
    # e.g. "CICMeeting" -> "CIC_Meeting"
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # split camel humps
    s2 = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1)
    snake = s2.replace("-", "_").lower()

    # naive pluralization if needed
    return snake if snake.endswith("s") else f"{snake}s"

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

def to_snake(name: str) -> str:
    """
    Convert CamelCase to snake_case, preserving acronyms:
      CICAgendaItem -> cic_agenda_item
      APIKey        -> api_key
    """
    s = _ACRONYM_BOUNDARY.sub(r'\1_\2', name)
    s = _MIDWORD_BOUNDARY.sub(r'\1_\2', s)
    return s.replace("__", "_").lower()

def pluralize_snake(s: str) -> str:
    """
    Very light pluralizer for route names.
    Keeps trailing 's' as-is; otherwise adds 's'.
    """
    return s if s.endswith('s') else f"{s}s"