
from __future__ import annotations
from typing import Any, Dict
from sqlalchemy.inspection import inspect
import datetime
from decimal import Decimal

def _serialize_value(v):
    if isinstance(v, (datetime.date, datetime.datetime, datetime.time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    try:
        import uuid
        if isinstance(v, uuid.UUID):
            return str(v)
    except Exception:
        pass
    return v

def to_dict(obj) -> Dict[str, Any]:
    mapper = inspect(obj).mapper
    data = {}
    for c in mapper.columns:
        data[c.key] = _serialize_value(getattr(obj, c.key))
    # Optionally include simple relationships (one-to-many omitted to avoid recursion)
    # for rel in mapper.relationships:
    #     if not rel.uselist and rel.key not in data:
    #         target = getattr(obj, rel.key)
    #         if target is not None:
    #             data[rel.key] = getattr(target, getattr(rel.target, "primary_key", [None])[0])
    return data
