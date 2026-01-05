from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.state_schemas import OSSSState

logger = get_logger(__name__)


# Router contract used by LangGraph add_conditional_edges:
# router(state: OSSSState) -> str
RouterFn = Callable[[OSSSState], str]


class RouterError(Exception):
    """Raised for router registry or execution errors."""


@dataclass(frozen=True)
class RouterSpec:
    """
    Optional metadata for introspection / docs / validation.
    """
    name: str
    description: str = ""


class RouterRegistry:
    """
    Central registry of named router functions.

    GraphFactory / PatternSpec refers to routers by string name.

    Contract Superset Mode (Option A):
      - Pattern names are canonical only ("standard", "data_query", ...).
      - Router names are contracts too: patterns.json references canonical router
        names (e.g. "refiner_route_query_or_end", "route_after_data_query").
      - Legacy aliases (e.g. "route_after_refiner") must NOT be required.
    """

    def __init__(self) -> None:
        self._routers: Dict[str, RouterFn] = {}
        self._specs: Dict[str, RouterSpec] = {}
        self.logger = get_logger(f"{__name__}.RouterRegistry")
        self.logger.debug("Initialized RouterRegistry", extra={"event": "router_registry_init"})

        # ✅ Option A: do NOT require legacy alias routers on startup.
        # We keep a tiny optional compat shim, but only if present.
        self._bootstrap_builtin_routers()

    def _bootstrap_builtin_routers(self) -> None:
        """
        ✅ Option A: Canonical-only bootstrap.

        - Do not "require" legacy alias routers (e.g. route_after_refiner).
        - If a legacy alias is present, you may register it for backward
          compatibility, but missing alias is NOT a warning-worthy condition.
        - Resilience rule:
            each candidate import/register is isolated; bootstrap continues.

        Why:
          In Contract Superset Mode, graph-patterns.json should reference
          canonical router names only (e.g. "refiner_route_query_or_end",
          "route_after_data_query"), so the registry should not attempt to
          enforce older alias contracts.
        """
        optional_aliases: list[tuple[str, str]] = [
            ("route_after_refiner", "BACKCOMPAT alias for refiner_route_query_or_end"),
        ]

        for router_name, desc in optional_aliases:
            if self.has(router_name):
                continue

            candidates: list[tuple[str, str]] = []
            if router_name == "route_after_refiner":
                candidates = [
                    # ✅ Prefer the alias wrapper if it exists (best introspection / future-proofing)
                    ("OSSS.ai.orchestration.routers.builtins", "route_after_refiner"),
                    # Fallback to canonical implementation
                    ("OSSS.ai.orchestration.routers.builtins", "router_refiner_query_or_end"),
                    # Older locations/names if you have historical wiring
                    ("OSSS.ai.orchestration.routers.refiner", "refiner_route_query_or_end"),
                    ("OSSS.ai.orchestration.routers.refiner", "router_refiner_query_or_end"),
                ]

            registered = False

            for mod_path, fn_name in candidates:
                try:
                    mod = __import__(mod_path, fromlist=[fn_name])
                    fn = getattr(mod, fn_name)

                    if not callable(fn):
                        raise TypeError(f"{mod_path}.{fn_name} is not callable (type={type(fn).__name__})")

                    self.register(router_name, fn, description=desc)

                    self.logger.debug(
                        "Auto-registered optional legacy router alias",
                        extra={
                            "event": "router_bootstrap_success_optional",
                            "router_name": router_name,
                            "source_module": mod_path,
                            "source_fn": fn_name,
                        },
                    )
                    registered = True
                    break

                except Exception as exc:
                    # Keep logs low-noise: only DEBUG for optional alias attempts.
                    self.logger.debug(
                        "Optional router alias not available (candidate failed)",
                        extra={
                            "event": "router_bootstrap_failed_optional",
                            "router_name": router_name,
                            "source_module": mod_path,
                            "source_fn": fn_name,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )

            # ✅ Option A: missing optional alias should be silent (no warning).
            if not registered:
                self.logger.debug(
                    "Optional router alias not registered (not required)",
                    extra={
                        "event": "router_bootstrap_missing_optional",
                        "router_name": router_name,
                        "available_routers": sorted(self._routers.keys()),
                    },
                )

    def register(self, name: str, fn: RouterFn, *, description: str = "") -> None:
        key = (name or "").strip()
        if not key:
            self.logger.error("Attempted to register router with empty name", extra={"event": "router_register_error"})
            raise RouterError("Router name cannot be empty")

        if not callable(fn):
            self.logger.error(
                "Attempted to register non-callable router",
                extra={"event": "router_register_error", "router_name": key, "fn_type": type(fn).__name__},
            )
            raise RouterError(f"Router '{key}' must be callable")

        if key in self._routers:
            self.logger.warning(
                "Overwriting existing router",
                extra={"event": "router_register_overwrite", "router_name": key},
            )

        self._routers[key] = fn
        self._specs[key] = RouterSpec(name=key, description=description or "")

        self.logger.debug(
            "Registered router",
            extra={
                "event": "router_registered",
                "router_name": key,
                "description": description or "",
                "available_routers": sorted(self._routers.keys()),
            },
        )

    def get(self, name: str) -> RouterFn:
        key = (name or "").strip()
        fn = self._routers.get(key)
        if fn is None:
            self.logger.error("Unknown router requested", extra={"event": "router_lookup_failed", "router_name": key})
            raise RouterError(f"Unknown router: {key}")

        self.logger.debug("Router lookup successful", extra={"event": "router_lookup", "router_name": key})
        return fn

    def has(self, name: str) -> bool:
        key = (name or "").strip()
        return key in self._routers

    def list_names(self) -> list[str]:
        return sorted(self._routers.keys())

    def spec(self, name: str) -> Optional[RouterSpec]:
        key = (name or "").strip()
        return self._specs.get(key)
