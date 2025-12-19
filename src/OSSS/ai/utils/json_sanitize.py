from __future__ import annotations

from typing import Any

def sanitize_for_json(obj: Any, *, max_depth: int = 8, max_str: int = 500) -> Any:
    """
    Convert `obj` into something JSON-serializable, removing circular references.
    - Cycles become "[circular]"
    - Depth is capped to avoid huge blobs
    - Unknown objects become a short repr()
    """

    seen: set[int] = set()

    def _short_repr(x: Any) -> str:
        try:
            s = repr(x)
        except Exception:
            s = f"<unreprable {type(x).__name__}>"
        if len(s) > max_str:
            s = s[:max_str] + "…"
        return s

    def _walk(x: Any, depth: int) -> Any:
        if depth <= 0:
            return "[max_depth]"

        # primitives
        if x is None or isinstance(x, (bool, int, float, str)):
            return x

        # common leaf types that should NOT participate in circular tracking
        try:
            from uuid import UUID
            if isinstance(x, UUID):
                return str(x)
        except Exception:
            pass

        try:
            import datetime as _dt
            if isinstance(x, (_dt.datetime, _dt.date, _dt.time)):
                # isoformat keeps it JSON-friendly
                return x.isoformat()
        except Exception:
            pass

        try:
            from decimal import Decimal
            if isinstance(x, Decimal):
                # safer than float; preserves exact value as string
                return str(x)
        except Exception:
            pass

        try:
            from enum import Enum
            if isinstance(x, Enum):
                return x.value if isinstance(x.value, (str, int, float, bool)) else str(x.value)
        except Exception:
            pass

        try:
            from pathlib import Path
            if isinstance(x, Path):
                return str(x)
        except Exception:
            pass

        if isinstance(x, (bytes, bytearray, memoryview)):
            # keep short + readable; avoid huge blobs
            b = bytes(x)
            if len(b) > 256:
                return f"[bytes {len(b)}]"
            return b.hex()

        # Only track things that can actually contain references / form cycles
        track = isinstance(x, (dict, list, tuple, set))
        if not track:
            # pydantic/dataclass/custom objects can also be cyclic
            if callable(getattr(x, "model_dump", None)):
                track = True
            else:
                try:
                    import dataclasses
                    if dataclasses.is_dataclass(x):
                        track = True
                except Exception:
                    pass

        if track:
            oid = id(x)
            if oid in seen:
                return "[circular]"
            seen.add(oid)

        # dict
        if isinstance(x, dict):
            out: dict[str, Any] = {}
            for k, v in x.items():
                ks = k if isinstance(k, str) else str(k)
                out[ks] = _walk(v, depth - 1)
            return out

        # list/tuple/set
        if isinstance(x, (list, tuple, set)):
            return [_walk(v, depth - 1) for v in x]

        # pydantic v2 models
        dump = getattr(x, "model_dump", None)
        if callable(dump):
            try:
                return _walk(x.model_dump(mode="python"), depth - 1)
            except Exception:
                return _short_repr(x)

        # dataclasses (DON'T use asdict() due to potential infinite recursion)
        try:
            import dataclasses
            if dataclasses.is_dataclass(x):
                out: dict[str, Any] = {}
                for f in dataclasses.fields(x):
                    try:
                        out[f.name] = _walk(getattr(x, f.name), depth - 1)
                    except Exception:
                        out[f.name] = "[unreadable]"
                return out
        except Exception:
            pass

        # generic objects: try __dict__ in a safe way
        d = getattr(x, "__dict__", None)
        if isinstance(d, dict):
            try:
                return _walk(d, depth - 1)
            except Exception:
                return _short_repr(x)

        # fallback
        return _short_repr(x)

    return _walk(obj, max_depth)


# Backwards-compatible / requested alias
_sanitize_for_json = sanitize_for_json
