from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import hashlib
import pathlib

from OSSS.ai.observability import get_logger
from .patterns.spec import PatternRegistry, GraphPattern


class PatternServiceError(Exception):
    pass


# ✅ Guardrails: compile variants / non-pattern tokens must never be treated as patterns
_RESERVED_NON_PATTERNS: set[str] = {
    "superset",
    "superset_nodes",
    "variant",
    "compile_variant",
}


@dataclass(frozen=True)
class PatternServiceConfig:
    patterns_path: str


class PatternService:
    """
    Option A (strict, no back-compat):

    - Single source of truth is cfg.patterns_path (GraphFactory decides the path).
    - load() is STRICT:
        * file must exist
        * file must be non-empty (after stripping whitespace)
        * registry.load_from_file() must succeed
    - get() is STRICT (normalized lowercase names)
    - require() is STRICT (unknown => raises)
    - fingerprint() is deterministic and safe (returns "nohash" on failure)
    """

    def __init__(self, cfg: PatternServiceConfig, *, registry: Optional[PatternRegistry] = None) -> None:
        self.logger = get_logger(f"{__name__}.PatternService")
        self.cfg = cfg
        self.registry = registry or PatternRegistry()
        self._loaded_path: Optional[str] = None
        self._loaded_fingerprint: Optional[str] = None

    def load(self) -> None:
        path = self.cfg.patterns_path
        p = pathlib.Path(path)

        self.logger.info("Loading graph patterns", extra={"path": path})

        if not p.exists():
            self.logger.error("Patterns file not found", extra={"path": path})
            raise PatternServiceError(f"Patterns file not found: {path}")

        try:
            # Option A strict: fail loudly if the file is empty/whitespace.
            raw_text = p.read_text(encoding="utf-8")
            if not raw_text.strip():
                self.logger.error("Patterns file is empty", extra={"path": path})
                raise PatternServiceError(f"Patterns file is empty: {path}")

            # Delegate parsing/validation to registry (single authority).
            self.registry.load_from_file(str(p))

            self._loaded_path = str(p)
            self._loaded_fingerprint = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]

            loaded = self.list_patterns()
            if not loaded:
                # Option A strict: if registry loaded nothing, treat as fatal.
                self.logger.error("No patterns loaded", extra={"path": path})
                raise PatternServiceError(f"No patterns loaded from: {path}")

            self.logger.info(
                "Graph patterns loaded",
                extra={
                    "path": path,
                    "bytes": len(raw_text.encode("utf-8")),
                    "fingerprint": self._loaded_fingerprint,
                    "loaded_patterns": loaded,
                },
            )
        except PatternServiceError:
            raise
        except Exception as e:
            self.logger.exception("Failed to load graph patterns", extra={"path": path, "error": str(e)})
            raise PatternServiceError(f"Failed to load patterns: {e}") from e

    def get(self, pattern_name: str) -> Optional[GraphPattern]:
        if not isinstance(pattern_name, str):
            raise TypeError("pattern_name must be str")
        name = pattern_name.strip().lower()
        if not name:
            raise ValueError("pattern_name must be non-empty")

        # ✅ Option A: patterns are contracts; compile strategies are NOT patterns
        if name in _RESERVED_NON_PATTERNS:
            raise PatternServiceError(
                f"{name!r} is not a valid pattern name. "
                "Option A: patterns are contracts; compile strategy must be expressed via "
                "compile_variant/agents_superset, not as a separate pattern."
            )

        return self.registry.get(name)

    def require(self, pattern_name: str) -> GraphPattern:
        """
        Option A strict helper: unknown patterns are fatal.

        Prefer this over get() at compile boundaries where a pattern must exist.
        """
        pat = self.get(pattern_name)
        if pat is None:
            raise PatternServiceError(f"Unknown graph pattern: {pattern_name.strip().lower()}")
        return pat

    def list_patterns(self) -> list[str]:
        """
        Best-effort list of loaded pattern names for logging/diagnostics.
        """
        reg = self.registry

        fn = getattr(reg, "list_patterns", None)
        if callable(fn):
            out = fn()
            return sorted([str(x).strip().lower() for x in out if str(x).strip()])

        # fallback: common storage shapes
        for attr in ("patterns", "_patterns"):
            raw = getattr(reg, attr, None)
            if isinstance(raw, dict):
                return sorted([str(k).strip().lower() for k in raw.keys() if str(k).strip()])

        return []

    def fingerprint(self) -> str:
        """
        Option A: fingerprint the *current* file contents.

        If load() succeeded, we return the loaded fingerprint when possible.
        """
        if self._loaded_fingerprint:
            return self._loaded_fingerprint

        path = self.cfg.patterns_path
        try:
            raw = pathlib.Path(path).read_bytes()
            return hashlib.sha256(raw).hexdigest()[:16]
        except Exception as e:
            self.logger.warning("Failed to compute patterns fingerprint; using 'nohash'", extra={"error": str(e)})
            return "nohash"
