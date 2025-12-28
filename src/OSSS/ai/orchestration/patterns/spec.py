"""
Graph pattern specification and resolution layer.

This module:
- Loads graph patterns from JSON
- Resolves conditional + static edges
- Enforces structural invariants (no early synthesis)
- Does NOT build LangGraph graphs directly

GraphFactory is the only place that mutates StateGraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional
import json
import pathlib
import logging  # <-- added

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger("OSSS.ai.orchestration.graph_patterns")  # <-- added

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Edge = Dict[str, str]
WhenExpr = str
RouterName = str

# conditional_destinations[from_node][router_output_key] = destination_node_or_END
ConditionalDestinations = Dict[str, Dict[str, str]]

# ---------------------------------------------------------------------------
# `when` expression evaluation (safe parser + tiny cache)
# ---------------------------------------------------------------------------


class WhenExprError(ValueError):
    pass


@dataclass(frozen=True)
class _Tok:
    kind: str  # "LPAREN","RPAREN","AND","OR","NOT","HAS","EOF"
    value: Optional[str] = None  # used for HAS(agent_name)


# Tiny cache: expr -> token list
# (tokenization is the expensive part; parsing is cheap and depends on `agents`)
_MAX_WHEN_CACHE = 256
_WHEN_TOK_CACHE: Dict[str, List[_Tok]] = {}


def evaluate_when_expr(expr: str, agents: set[str]) -> bool:
    """
    Safe evaluator for `when` expressions.

    Supported:
      - has('agent') or has("agent")
      - not <expr>
      - <expr> and <expr>
      - <expr> or <expr>
      - parentheses: ( ... )

    Precedence:
      not > and > or
    """
    expr_orig = expr  # <-- added (for logging)
    expr = (expr or "").strip()
    if not expr:
        logger.debug(  # <-- added
            "[when] empty or missing expression treated as True",
            extra={"expr": expr_orig, "agents": sorted(agents)},
        )
        return True

    try:  # <-- added
        toks = _get_or_tokenize_when(expr)
        parser = _WhenParser(toks, agents)
        result = parser.parse_expr()

        # Must consume all tokens
        if parser.peek().kind != "EOF":
            raise WhenExprError(f"Unexpected token after expression: {parser.peek().kind}")

        logger.debug(  # <-- added
            "[when] evaluated expression",
            extra={"expr": expr_orig, "agents": sorted(agents), "result": result},
        )
        return result
    except WhenExprError as e:  # <-- added
        logger.warning(
            "[when] error evaluating expression; defaulting to False",
            extra={"expr": expr_orig, "agents": sorted(agents), "error": str(e)},
        )
        return False  # conservative when expression is malformed


def _get_or_tokenize_when(expr: str) -> List[_Tok]:
    """
    Tokenize + tiny cache so repeated identical `when` strings
    don't re-scan the same text.
    """
    cached = _WHEN_TOK_CACHE.get(expr)
    if cached is not None:
        return cached

    toks = _tokenize_when(expr)

    # tiny bounded cache (cheap eviction)
    if len(_WHEN_TOK_CACHE) >= _MAX_WHEN_CACHE:
        # pop an arbitrary (oldest insertion order is preserved in Py3.7+ dicts)
        popped_key, _ = _WHEN_TOK_CACHE.popitem(last=False) if hasattr(_WHEN_TOK_CACHE, "popitem") else (_WHEN_TOK_CACHE.pop(next(iter(_WHEN_TOK_CACHE))), None)  # type: ignore[assignment]  # <-- added (defensive)
        logger.debug(  # <-- added
            "[when] evicted expression from token cache",
            extra={"evicted_expr": popped_key, "cache_size": len(_WHEN_TOK_CACHE)},
        )
    _WHEN_TOK_CACHE[expr] = toks
    logger.debug(  # <-- added
        "[when] tokenized new expression",
        extra={"expr": expr, "token_count": len(toks)},
    )
    return toks


def _tokenize_when(s: str) -> List[_Tok]:
    i = 0
    n = len(s)
    out: List[_Tok] = []

    def skip_ws() -> None:
        nonlocal i
        while i < n and s[i].isspace():
            i += 1

    def match_kw(kw: str) -> bool:
        nonlocal i
        if s[i : i + len(kw)].lower() != kw:
            return False
        # ensure word boundary
        before_ok = (i == 0) or s[i - 1].isspace() or s[i - 1] in "()"
        after_i = i + len(kw)
        after_ok = (after_i >= n) or s[after_i].isspace() or s[after_i] in "()"
        return before_ok and after_ok

    def parse_has() -> _Tok:
        # expecting: has('name') or has("name")
        nonlocal i
        # consume "has"
        i += 3
        skip_ws()
        if i >= n or s[i] != "(":
            raise WhenExprError("Expected '(' after has")
        i += 1
        skip_ws()
        if i >= n or s[i] not in ("'", '"'):
            raise WhenExprError("Expected quoted agent name in has('...')")

        quote = s[i]
        i += 1
        start = i
        while i < n and s[i] != quote:
            i += 1
        if i >= n:
            raise WhenExprError("Unterminated string in has(...)")

        name = s[start:i].strip().lower()
        i += 1  # closing quote

        skip_ws()
        if i >= n or s[i] != ")":
            raise WhenExprError("Expected ')' to close has(...)")
        i += 1

        return _Tok("HAS", name)

    while True:
        skip_ws()
        if i >= n:
            out.append(_Tok("EOF"))
            return out

        ch = s[i]

        if ch == "(":
            out.append(_Tok("LPAREN"))
            i += 1
            continue

        if ch == ")":
            out.append(_Tok("RPAREN"))
            i += 1
            continue

        if match_kw("and"):
            out.append(_Tok("AND"))
            i += 3
            continue

        if match_kw("or"):
            out.append(_Tok("OR"))
            i += 2
            continue

        if match_kw("not"):
            out.append(_Tok("NOT"))
            i += 3
            continue

        if s[i : i + 3].lower() == "has":
            out.append(parse_has())
            continue

        snippet = s[i : min(i + 20, n)]
        raise WhenExprError(f"Unexpected token near: {snippet!r}")


class _WhenParser:
    def __init__(self, toks: List[_Tok], agents: set[str]) -> None:
        self.toks = toks
        self.i = 0
        self.agents = agents

    def peek(self) -> _Tok:
        return self.toks[self.i]

    def pop(self, kind: Optional[str] = None) -> _Tok:
        tok = self.peek()
        if kind and tok.kind != kind:
            raise WhenExprError(f"Expected {kind}, got {tok.kind}")
        self.i += 1
        return tok

    # Grammar (precedence climbing):
    # expr     := or_expr
    # or_expr  := and_expr (OR and_expr)*
    # and_expr := unary (AND unary)*
    # unary    := NOT unary | primary
    # primary  := HAS | LPAREN expr RPAREN

    def parse_expr(self) -> bool:
        return self.parse_or()

    def parse_or(self) -> bool:
        left = self.parse_and()
        while self.peek().kind == "OR":
            self.pop("OR")
            right = self.parse_and()
            left = bool(left or right)
        return left

    def parse_and(self) -> bool:
        left = self.parse_unary()
        while self.peek().kind == "AND":
            self.pop("AND")
            right = self.parse_unary()
            left = bool(left and right)
        return left

    def parse_unary(self) -> bool:
        if self.peek().kind == "NOT":
            self.pop("NOT")
            return not self.parse_unary()
        return self.parse_primary()

    def parse_primary(self) -> bool:
        tok = self.peek()

        if tok.kind == "HAS":
            self.pop("HAS")
            name = (tok.value or "").lower()
            return name in self.agents

        if tok.kind == "LPAREN":
            self.pop("LPAREN")
            val = self.parse_expr()
            self.pop("RPAREN")
            return val

        raise WhenExprError(f"Expected has(...) or '(', got {tok.kind}")


# ---------------------------------------------------------------------------
# Pattern model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GraphPattern:
    """
    Declarative description of a graph pattern.

    A pattern contains:
    - entry_point
    - static edges
    - optional conditional routers (by name)
    - optional conditional destination maps (router outputs -> destinations)

    NOTE:
      conditional_edges defines "where the fork happens"
      edges defines "everything else"
      conditional_destinations defines "router return keys -> where they go"
    """

    name: str
    description: str
    entry_point: Optional[str]
    edges: List[Edge]
    conditional_edges: Dict[str, RouterName]
    conditional_destinations: ConditionalDestinations

    def resolve_edges(self, agents: Iterable[str]) -> List[Edge]:
        agent_set = {a.lower() for a in agents}
        resolved: List[Edge] = []

        logger.info(  # <-- added
            "[pattern] resolve_edges start",
            extra={
                "pattern_name": self.name,
                "entry_point": (self.entry_point or "").lower() if self.entry_point else None,
                "agent_set": sorted(agent_set),
                "raw_edge_count": len(self.edges),
            },
        )

        for edge in self.edges:
            raw_from = edge.get("from", "")
            raw_to = edge.get("to", "")
            frm = str(raw_from).lower()
            to = str(raw_to).lower()

            if not frm or not to:
                logger.debug(  # <-- added
                    "[pattern] skipping edge with missing from/to",
                    extra={"pattern_name": self.name, "edge": edge},
                )
                continue

            # enforce "nodes must exist" (END is allowed)
            if frm != "end" and frm not in agent_set:
                logger.debug(  # <-- added
                    "[pattern] skipping edge: from_node not in agent_set",
                    extra={
                        "pattern_name": self.name,
                        "edge": edge,
                        "agent_set": sorted(agent_set),
                    },
                )
                continue
            if to != "end" and to not in agent_set:
                logger.debug(  # <-- added
                    "[pattern] skipping edge: to_node not in agent_set",
                    extra={
                        "pattern_name": self.name,
                        "edge": edge,
                        "agent_set": sorted(agent_set),
                    },
                )
                continue

            if not self._edge_is_active(edge, agent_set):
                logger.debug(  # <-- added
                    "[pattern] skipping edge: when-expression evaluated to False",
                    extra={"pattern_name": self.name, "edge": edge},
                )
                continue

            logger.debug(  # <-- added
                "[pattern] including edge",
                extra={"pattern_name": self.name, "from": frm, "to": to, "edge": edge},
            )
            resolved.append({"from": frm, "to": to})

        self._validate_no_early_synthesis(resolved, agent_set)

        logger.info(  # <-- added
            "[pattern] resolve_edges completed",
            extra={
                "pattern_name": self.name,
                "resolved_edge_count": len(resolved),
                "resolved_edges": resolved,
                "agent_set": sorted(agent_set),
            },
        )

        return resolved

    def _edge_is_active(self, edge: Edge, agents: set[str]) -> bool:
        when: Optional[WhenExpr] = edge.get("when")
        if not when:
            return True
        active = evaluate_when_expr(when, agents)
        logger.debug(  # <-- added
            "[pattern] evaluated edge 'when' expression",
            extra={
                "pattern_name": self.name,
                "edge": edge,
                "agents": sorted(agents),
                "active": active,
            },
        )
        return active

    def _validate_no_early_synthesis(self, edges: List[Edge], agents: set[str]) -> None:
        if "data_query" not in agents or "synthesis" not in agents:
            return

        for e in edges:
            if e["to"] == "synthesis" and e["from"] == "refiner":
                logger.error(  # <-- added
                    "[pattern] invalid refiner→synthesis edge while data_query present",
                    extra={
                        "pattern_name": self.name,
                        "edge": e,
                        "agents": sorted(agents),
                    },
                )
                raise ValueError(
                    f"[pattern:{self.name}] invalid edge refiner→synthesis "
                    f"while data_query is present"
                )

    def has_conditional(self) -> bool:
        has_cond = bool(self.conditional_edges)
        logger.debug(  # <-- added
            "[pattern] has_conditional check",
            extra={"pattern_name": self.name, "has_conditional": has_cond},
        )
        return has_cond

    def get_entry_point(self, agents: Iterable[str]) -> Optional[str]:
        if not self.entry_point:
            logger.debug(  # <-- added
                "[pattern] get_entry_point: no entry_point configured",
                extra={"pattern_name": self.name},
            )
            return None
        ep = self.entry_point.lower()
        agent_set = {a.lower() for a in agents}
        if ep in agent_set:
            logger.info(  # <-- added
                "[pattern] resolved entry point",
                extra={"pattern_name": self.name, "entry_point": ep},
            )
            return ep
        logger.warning(  # <-- added
            "[pattern] entry point not in agent_set",
            extra={
                "pattern_name": self.name,
                "configured_entry_point": ep,
                "agent_set": sorted(agent_set),
            },
        )
        return None

    def get_conditional_destinations_for(self, from_node: str) -> Dict[str, str]:
        from_key = (from_node or "").lower()
        dest = self.conditional_destinations.get(from_key, {})
        logger.debug(  # <-- added
            "[pattern] get_conditional_destinations_for",
            extra={
                "pattern_name": self.name,
                "from_node": from_node,
                "resolved_key": from_key,
                "destinations": dest,
            },
        )
        return dest


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

class PatternRegistry:
    """
    Loads and stores all graph patterns.
    """

    def __init__(self, pattern_file: Optional[str] = None) -> None:
        self._patterns: Dict[str, GraphPattern] = {}
        if pattern_file:
            self.load_from_file(pattern_file)

    def load_from_file(self, path: str) -> None:
        path_obj = pathlib.Path(path)  # <-- changed variable name
        logger.info(  # <-- added
            "[patterns] loading graph patterns from file",
            extra={"path": str(path_obj)},
        )

        with path_obj.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        patterns = raw.get("patterns", {}) or {}
        for name, spec in patterns.items():
            gp = self._parse_pattern(str(name), spec or {})
            self._patterns[str(name)] = gp

        logger.info(  # <-- added
            "[patterns] loaded graph patterns",
            extra={
                "path": str(path_obj),
                "pattern_names": sorted(self._patterns.keys()),
                "standard_edges_preview": [
                    e for e in self._patterns.get("standard", GraphPattern("standard", "", None, [], {}, {})).edges
                ][:5]
                if "standard" in self._patterns
                else None,
            },
        )

    def _parse_pattern(self, name: str, spec: Dict[str, Any]) -> GraphPattern:
        raw_cd = spec.get("conditional_destinations", {}) or {}
        cd: ConditionalDestinations = {}

        if isinstance(raw_cd, dict):
            for from_node, mapping in raw_cd.items():
                if not from_node or not isinstance(mapping, dict):
                    continue
                from_key = str(from_node).lower()
                cd[from_key] = {}
                for out_key, dest in mapping.items():
                    if out_key is None or dest is None:
                        continue
                    cd[from_key][str(out_key)] = str(dest)

        pattern = GraphPattern(
            name=name,
            description=str(spec.get("description", "") or ""),
            entry_point=spec.get("entry_point"),
            edges=spec.get("edges", []) or [],
            conditional_edges=spec.get("conditional_edges", {}) or {},
            conditional_destinations=cd,
        )

        logger.debug(  # <-- added
            "[patterns] parsed pattern",
            extra={
                "pattern_name": name,
                "description": pattern.description,
                "entry_point": pattern.entry_point,
                "edge_count": len(pattern.edges),
                "conditional_edges_keys": list(pattern.conditional_edges.keys()),
                "conditional_destinations_keys": list(pattern.conditional_destinations.keys()),
            },
        )

        return pattern

    def get(self, name: str) -> Optional[GraphPattern]:
        gp = self._patterns.get(name)
        logger.info(  # <-- added
            "[patterns] get pattern",
            extra={
                "requested_name": name,
                "found": gp is not None,
                "available_patterns": sorted(self._patterns.keys()),
            },
        )
        return gp

    def list_names(self) -> List[str]:
        names = sorted(self._patterns.keys())
        logger.debug(  # <-- added
            "[patterns] list_names",
            extra={"pattern_names": names},
        )
        return names


# ---------------------------------------------------------------------------
# Router registry (name → callable)
# ---------------------------------------------------------------------------

RouterFn = Callable[[Any], str]


class RouterRegistry:
    """
    Maps router names to callables.

    Used only by GraphFactory during conditional wiring.
    """

    def __init__(self) -> None:
        self._routers: Dict[str, RouterFn] = {}

    def register(self, name: str, fn: RouterFn) -> None:
        logger.info(  # <-- added
            "[routers] register router",
            extra={"name": name, "fn_repr": repr(fn)},
        )
        self._routers[name] = fn

    def get(self, name: str) -> RouterFn:
        if name not in self._routers:
            logger.error(  # <-- added
                "[routers] unknown router requested",
                extra={"name": name, "known_routers": list(self._routers.keys())},
            )
            raise KeyError(f"Unknown router: {name}")
        logger.debug(  # <-- added
            "[routers] get router",
            extra={"name": name},
        )
        return self._routers[name]
