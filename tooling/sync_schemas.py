#!/usr/bin/env python3

"""
Generate Pydantic schema modules for each SQLAlchemy model in OSSS.
- Handles Pydantic v1/v2
- Attempts good defaults for nullable / defaults
- Adds created_at / updated_at to the *Read* model
"""
from __future__ import annotations

import os
import sys
import re
import json
import inspect
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

# ---- Configuration ----
MODELS_PACKAGE = os.getenv("OSSS_MODELS_PKG", "OSSS.db.models")
SCHEMAS_DIR = Path(os.getenv("OSSS_SCHEMAS_DIR", "src/OSSS/schemas"))
SERVER_MANAGED_FIELDS: Set[str] = {"created_at", "updated_at"}
INCLUDE_COLUMNS_IN_CREATE: Set[str] = set()  # columns to force-include in Create

# If your project uses a common Base class in a known module, it helps to import it
# but it's not strictly required — we detect models via presence of __table__.

# ---- Utilities ----
def snake_case(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def detect_pydantic_major() -> int:
    try:
        import pydantic
        v = getattr(pydantic, "__version__", "2")
        major = int(str(v).split(".")[0])
        return major
    except Exception:
        return 2

PYDANTIC_MAJOR = detect_pydantic_major()

# SQLAlchemy type mapping (basic)
from sqlalchemy import Integer, BigInteger, SmallInteger, String, Text, Boolean, DateTime, Date, Float, Numeric
try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB, ARRAY as PG_ARRAY
except Exception:
    PG_UUID = None
    PG_JSONB = None
    PG_ARRAY = None

def py_type_for_column(col) -> str:
    """Return a Python type annotation (string) for a SA Column."""
    t = col.type
    # Postgres special types
    if PG_UUID and isinstance(t, PG_UUID):
        py = "UUID"
    elif PG_JSONB and isinstance(t, PG_JSONB):
        py = "dict"
    elif PG_ARRAY and isinstance(t, PG_ARRAY):
        subtype = "Any"
        try:
            if hasattr(t, "item_type"):
                base = t.item_type
                if isinstance(base, Integer):
                    subtype = "int"
                elif isinstance(base, String):
                    subtype = "str"
                elif isinstance(base, Boolean):
                    subtype = "bool"
                elif isinstance(base, Float):
                    subtype = "float"
            py = f"list[{subtype}]"
        except Exception:
            py = "list[Any]"
    elif isinstance(t, (Integer, SmallInteger, BigInteger)):
        py = "int"
    elif isinstance(t, (Float, Numeric)):
        py = "float"
    elif isinstance(t, (String, Text)):
        py = "str"
    elif isinstance(t, Boolean):
        py = "bool"
    elif isinstance(t, DateTime):
        py = "datetime"
    elif isinstance(t, Date):
        py = "date"
    else:
        # fallback
        py = "Any"
    # make optional if nullable
    if getattr(col, "nullable", False):
        py = f"Optional[{py}]"
    return py

def default_for_column(col) -> Optional[str]:
    """
    Returns a default expression string for Field(...), or None.
    For server-managed timestamps, we usually leave defaults to the server/ORM.
    """
    # If Column has server_default or onupdate etc., skip explicit default
    if getattr(col, "server_default", None) is not None:
        return None
    if getattr(col, "default", None) is not None:
        # can't easily render SA defaults; make it Optional with None
        return "None"
    if getattr(col, "nullable", False):
        return "None"
    return None  # required

def collect_models() -> Dict[str, Any]:
    """
    Import the models package and return {ModelName: class} for mapped classes
    that have __table__.
    """
    pkg = importlib.import_module(MODELS_PACKAGE)
    # Recursively import submodules to register all models
    pkg_path = Path(pkg.__file__).parent
    for p in pkg_path.glob("*.py"):
        if p.name.startswith("_") or p.name == "__init__.py":
            continue
        mod_name = f"{MODELS_PACKAGE}.{p.stem}"
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            print(f"[WARN] Failed to import {mod_name}: {e}")

    # Walk pkg attributes
    models: Dict[str, Any] = {}
    for name, obj in vars(pkg).items():
        if inspect.ismodule(obj):
            for n2, c in vars(obj).items():
                if inspect.isclass(c) and hasattr(c, "__table__"):
                    models[n2] = c
    # also scan package namespace directly for re-exported classes
    for n2, c in vars(pkg).items():
        if inspect.isclass(c) and hasattr(c, "__table__"):
            models[n2] = c
    return models

def split_fields(model) -> Tuple[List[Any], List[Any], Optional[str]]:
    """
    Returns (columns, pkey_columns, id_name_if_any).
    """
    cols = list(model.__table__.columns)
    pks = [c for c in cols if c.primary_key]
    id_name = None
    for c in pks:
        if c.name == "id":
            id_name = "id"
            break
    return cols, pks, id_name

def render_field_line(col, *, for_model: str) -> str:
    """
    Build `name: Type = Field(...)` (or v1 compatible) for a single column.
    for_model: "base" | "create" | "update" | "read"
    """
    name = col.name
    py_t = py_type_for_column(col)
    # Update model: everything optional
    if for_model == "update" and not py_t.startswith("Optional["):
        py_t = f"Optional[{py_t}]"
    # Create model: skip server-managed unless forced
    if for_model == "create" and name in SERVER_MANAGED_FIELDS and name not in INCLUDE_COLUMNS_IN_CREATE:
        return ""
    # Base: exclude server-managed
    if for_model == "base" and name in SERVER_MANAGED_FIELDS:
        return ""
    # Read: include everything
    # Defaults
    dflt = default_for_column(col)
    # Pydantic syntax
    if PYDANTIC_MAJOR >= 2:
        if dflt is None:
            rhs = "Field(...)"
        else:
            rhs = f"Field({dflt})"
    else:
        # v1
        if dflt is None:
            rhs = "..."  # Required
        else:
            rhs = dflt
    return f"    {name}: {py_t} = {rhs}"

def build_model_code(name: str, model) -> str:
    """
    Generate the content of a schema module for a single SQLAlchemy model.
    """
    cols, pks, id_name = split_fields(model)
    # Sort columns by appearance (already in table order)
    # Identify fields to render for each class
    def non_pk(c): return not c.primary_key

    base_lines = []
    create_lines = []
    update_lines = []
    read_lines = []

    for c in cols:
        # Always render body for read; base/create/update conditionally
        # Primary key: typically only in Read
        if c.primary_key and c.name != "id":
            # still include in Read
            pass
        # Base
        ln = render_field_line(c, for_model="base")
        if ln: base_lines.append(ln)
        # Create
        if (not c.primary_key) or (c.name in INCLUDE_COLUMNS_IN_CREATE):
            ln = render_field_line(c, for_model="create")
            if ln: create_lines.append(ln)
        # Update
        ln = render_field_line(c, for_model="update")
        if ln: update_lines.append(ln)
        # Read
        ln = render_field_line(c, for_model="read")
        if ln: read_lines.append(ln)

    # Ensure id and timestamps are present in Read if they exist
    # (they will be, due to "read" branch above)

    # Imports
    imports = [
        "from __future__ import annotations",
        "from typing import Optional, Any, List, Dict, Union",
        "from datetime import datetime, date",
    ]
    if PYDANTIC_MAJOR >= 2:
        imports.append("from pydantic import BaseModel, Field, ConfigDict")
    else:
        imports.append("from pydantic import BaseModel, Field")

    # Top matter
    header = "\\n".join(imports) + "\\n\\n"
    class_name_base = f"{name}Base"
    class_name_create = f"{name}Create"
    class_name_update = f"{name}Update"
    class_name_read = f"{name}Read"

    base = [f"class {class_name_base}(BaseModel):"]
    base.extend(base_lines or ["    pass"])

    create = [f"class {class_name_create}(BaseModel):"]
    create.extend(create_lines or ["    pass"])

    update = [f"class {class_name_update}(BaseModel):"]
    update.extend(update_lines or ["    pass"])

    read = [f"class {class_name_read}(BaseModel):"]
    read.extend(read_lines or ["    pass"])

    if PYDANTIC_MAJOR >= 2:
        # Pydantic v2 model config
        base.append("    model_config = ConfigDict(from_attributes=True)")
        create.append("    model_config = ConfigDict(from_attributes=True)")
        update.append("    model_config = ConfigDict(from_attributes=True)")
        read.append("    model_config = ConfigDict(from_attributes=True)")
    else:
        # v1
        for block in (base, create, update, read):
            block.append("")
            block.append("    class Config:")
            block.append("        orm_mode = True")

    parts = [header, "\\n".join(base), "\\n\\n", "\\n".join(create), "\\n\\n", "\\n".join(update), "\\n\\n", "\\n".join(read), "\\n"]
    return "".join(parts)

def main() -> int:
    # Ensure schemas dir exists
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    # Discover models
    models = collect_models()
    if not models:
        print(f"[ERROR] No models discovered under {MODELS_PACKAGE}. Is PYTHONPATH set?")
        return 2

    written: List[str] = []
    for cls_name, cls in sorted(models.items()):
        try:
            # Must be a declarative model with __table__
            if not hasattr(cls, "__table__"):
                continue
            table = getattr(cls, "__tablename__", None)
            # Skip association tables without proper __tablename__
            if not table:
                continue
            # Skip SQLAlchemy internal/index models etc. if any filter needed
            outfile = SCHEMAS_DIR / f"{snake_case(cls_name)}.py"
            code = build_model_code(cls_name, cls)
            outfile.write_text(code, encoding="utf-8")
            written.append(outfile.name)
            print(f"[OK] Wrote {outfile}")
        except Exception as e:
            print(f"[WARN] Skipped {cls_name}: {e}")

    # Update __init__.py
    init_path = SCHEMAS_DIR / "__init__.py"
    lines = ["# auto-generated exports\\n"]
    for fn in sorted(written):
        mod = Path(fn).stem
        # "from .asset_part import AssetPartBase, AssetPartCreate, ..."
        # We don't know class names at import time here, so export modules instead.
        lines.append(f"from .{mod} import *")
    init_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    print(f"[OK] Updated {init_path}")
    print(f"[DONE] Generated {len(written)} schema modules.")
    return 0

if __name__ == "__main__":
    # allow running from repo root (so `src` is importable)
    here = Path.cwd()
    src = here / "src"
    if src.exists():
        sys.path.insert(0, str(src))
    sys.exit(main())
