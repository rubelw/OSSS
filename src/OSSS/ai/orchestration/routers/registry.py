# OSSS/ai/orchestration/routers/registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set

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

    # ✅ Optional: declare allowed outputs for this router (if you want stricter safety)
    allowed_outputs: Optional[Set[str]] = None
    fallback_output: Optional[str] = None


def _canon_name(name: str) -> str:
    # ✅ best-practice: router names are contracts; normalize for lookups
    return (name or "").strip().lower()


def _canon_return(x: object) -> str:
    # ✅ enforce the contract type: must be a string branch key
    if isinstance(x, str):
        return x.strip()
    return ""


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
        self._bootstrap_builtin_routers()

    # -------------------------------------------------------------------------
    # Bootstrap
    # -------------------------------------------------------------------------

    def _bootstrap_builtin_routers(self) -> None:
        """
        ✅ Option A: Canonical-only bootstrap.

        - Do not "require" legacy alias routers (e.g. route_after_refiner).
        - If a legacy alias is present, you may register it for backward
          compatibility, but missing alias is NOT a warning-worthy condition.
        - Resilience rule:
            each candidate import/register is isolated; bootstrap continues.
        """
        optional_aliases: list[tuple[str, str]] = [
            ("route_after_refiner", "BACKCOMPAT alias for refiner_route_query_or_end"),
        ]

        for router_name, desc in optional_aliases:
            key = _canon_name(router_name)
            if self.has(key):
                continue

            candidates: list[tuple[str, str]] = []
            if key == "route_after_refiner":
                candidates = [
                    ("OSSS.ai.orchestration.routers.builtins", "route_after_refiner"),
                    ("OSSS.ai.orchestration.routers.builtins", "router_refiner_query_or_end"),
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

                    self.register(key, fn, description=desc)

                    self.logger.debug(
                        "Auto-registered optional legacy router alias",
                        extra={
                            "event": "router_bootstrap_success_optional",
                            "router_name": key,
                            "source_module": mod_path,
                            "source_fn": fn_name,
                        },
                    )
                    registered = True
                    break

                except Exception as exc:
                    self.logger.debug(
                        "Optional router alias not available (candidate failed)",
                        extra={
                            "event": "router_bootstrap_failed_optional",
                            "router_name": key,
                            "source_module": mod_path,
                            "source_fn": fn_name,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )

            if not registered:
                self.logger.debug(
                    "Optional router alias not registered (not required)",
                    extra={
                        "event": "router_bootstrap_missing_optional",
                        "router_name": key,
                        "available_routers": sorted(self._routers.keys()),
                    },
                )

    # -------------------------------------------------------------------------
    # Registration / Lookup
    # -------------------------------------------------------------------------

    def register(
        self,
        name: str,
        fn: RouterFn,
        *,
        description: str = "",
        allowed_outputs: Optional[Set[str]] = None,
        fallback_output: Optional[str] = None,
    ) -> None:
        key = _canon_name(name)
        if not key:
            self.logger.error("Attempted to register router with empty name", extra={"event": "router_register_error"})
            raise RouterError("Router name cannot be empty")

        if not callable(fn):
            self.logger.error(
                "Attempted to register non-callable router",
                extra={"event": "router_register_error", "router_name": key, "fn_type": type(fn).__name__},
            )
            raise RouterError(f"Router '{key}' must be callable")

        if allowed_outputs is not None and not isinstance(allowed_outputs, set):
            allowed_outputs = set(allowed_outputs)

        if fallback_output is not None and not isinstance(fallback_output, str):
            fallback_output = str(fallback_output)

        if key in self._routers:
            self.logger.warning(
                "Overwriting existing router",
                extra={"event": "router_register_overwrite", "router_name": key},
            )

        self._routers[key] = fn
        self._specs[key] = RouterSpec(
            name=key,
            description=description or "",
            allowed_outputs=allowed_outputs,
            fallback_output=(fallback_output.strip() if isinstance(fallback_output, str) else None),
        )

        self.logger.debug(
            "Registered router",
            extra={
                "event": "router_registered",
                "router_name": key,
                "description": description or "",
                "allowed_outputs": sorted(list(allowed_outputs)) if allowed_outputs else None,
                "fallback_output": fallback_output,
                "available_routers": sorted(self._routers.keys()),
            },
        )

    def get(self, name: str) -> RouterFn:
        key = _canon_name(name)
        fn = self._routers.get(key)
        if fn is None:
            self.logger.error("Unknown router requested", extra={"event": "router_lookup_failed", "router_name": key})
            raise RouterError(f"Unknown router: {key}")

        self.logger.debug("Router lookup successful", extra={"event": "router_lookup", "router_name": key})
        return fn

    def has(self, name: str) -> bool:
        key = _canon_name(name)
        return key in self._routers

    def list_names(self) -> list[str]:
        return sorted(self._routers.keys())

    def spec(self, name: str) -> Optional[RouterSpec]:
        key = _canon_name(name)
        return self._specs.get(key)

    # -------------------------------------------------------------------------
    # ✅ Best-practice: safe execution wrapper (optional)
    # -------------------------------------------------------------------------

    def call(self, name: str, state: OSSSState) -> str:
        """
        Execute a router by name with:
          - exception safety (fallback)
          - output type safety (must be str)
          - optional allowed_outputs validation

        This does NOT change LangGraph’s API, but you can use this from
        GraphFactory / node wrappers if you want stricter behavior.

        If you don't use it anywhere, it's harmless.
        """
        key = _canon_name(name)
        fn = self.get(key)
        spec = self._specs.get(key)

        fallback = (spec.fallback_output if spec else None) or "END"

        try:
            raw = fn(state)
        except Exception as exc:
            self.logger.exception(
                "Router execution failed; using fallback",
                extra={"event": "router_call_failed", "router_name": key, "fallback": fallback, "error": str(exc)},
            )
            return fallback

        out = _canon_return(raw)
        if not out:
            self.logger.error(
                "Router returned non-string/empty; using fallback",
                extra={"event": "router_call_bad_return", "router_name": key, "raw": str(raw), "fallback": fallback},
            )
            return fallback

        allowed = (spec.allowed_outputs if spec else None)
        if allowed and out not in allowed:
            self.logger.error(
                "Router returned disallowed output; using fallback",
                extra={
                    "event": "router_call_disallowed_output",
                    "router_name": key,
                    "output": out,
                    "allowed": sorted(list(allowed)),
                    "fallback": fallback,
                },
            )
            return fallback

        return out
