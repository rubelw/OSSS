#!/usr/bin/env python3

# scripts/check_schema_coverage.py
from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections import defaultdict

# --- Adjust if your package name changes ---
MODELS_PKG = "OSSS.db.models"
SCHEMAS_PKG = "OSSS.schemas"

def walk_classes(package: str):
    pkg = importlib.import_module(package)
    for _, modname, ispkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        if ispkg:
            continue
        try:
            m = importlib.import_module(modname)
        except Exception as e:
            print(f"[skip] {modname}: {e}")
            continue
        for name, obj in inspect.getmembers(m, inspect.isclass):
            yield modname, name, obj

def main():
    # Import Base and BaseModel lazily (so the import above can succeed)
    from OSSS.db.base import Base
    try:
        from pydantic import BaseModel  # pydantic v2
    except Exception:  # fallback just in case
        from pydantic.main import BaseModel

    model_modules: dict[str, str] = {}
    models: set[str] = set()

    # Collect SQLAlchemy models (exclude mixins/abstracts)
    for mod, name, cls in walk_classes(MODELS_PKG):
        try:
            if issubclass(cls, Base) and getattr(cls, "__tablename__", None):
                models.add(name)
                model_modules[name] = mod
        except Exception:
            pass

    # Collect Pydantic schemas
    create_for: dict[str, str] = {}   # model name -> module
    out_for: dict[str, str] = {}

    for mod, name, cls in walk_classes(SCHEMAS_PKG):
        try:
            if not issubclass(cls, BaseModel):
                continue
        except Exception:
            continue

        if name.endswith("Create"):
            create_for[name[:-6]] = mod
        if name.endswith("Out"):
            out_for[name[:-3]] = mod

    missing_create = sorted(models - set(create_for))
    missing_out = sorted(models - set(out_for))
    orphan_schemas = sorted((set(create_for) | set(out_for)) - models)

    print("\n=== MODELS DISCOVERED ===")
    for m in sorted(models):
        print(f"- {m}  ({model_modules.get(m,'?')})")

    print("\n=== MISSING Create SCHEMAS ===")
    if not missing_create:
        print("✓ None")
    else:
        for m in missing_create:
            print(f"- {m}  (expected class: {m}Create)")

    print("\n=== MISSING Out SCHEMAS ===")
    if not missing_out:
        print("✓ None")
    else:
        for m in missing_out:
            print(f"- {m}  (expected class: {m}Out)")

    print("\n=== ORPHAN SCHEMAS (no matching model) ===")
    if not orphan_schemas:
        print("✓ None")
    else:
        for n in orphan_schemas:
            cmod = create_for.get(n)
            omod = out_for.get(n)
            where = cmod or omod or "?"
            print(f"- {n}Create/{n}Out in {where}")

    # Helpful “to-do” stubs
    if missing_create or missing_out:
        print("\n=== SUGGESTED STUBS ===")
        for m in missing_create:
            print(f"\n# schemas/{m.lower()}.py -> add:")
            print(f"class {m}Create(BaseModel):")
            print("    # TODO: fill fields used on POST/PUT")
            print("    pass")

        for m in missing_out:
            print(f"\n# schemas/{m.lower()}.py -> add:")
            print(f"class {m}Out(ORMBase):")
            print("    # TODO: fill fields returned to clients (read-only fields OK)")
            print("    pass")

if __name__ == "__main__":
    main()
