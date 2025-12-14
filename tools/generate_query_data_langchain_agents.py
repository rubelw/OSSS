#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


DEBUG = os.getenv("DEBUG", "1").strip().lower() in {"1", "true", "yes", "y", "on"}
DEBUG_AST = os.getenv("DEBUG_AST", "0").strip().lower() in {"1", "true", "yes", "y", "on"}
DRY_RUN = os.getenv("DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "y", "on"}


def _dbg(msg: str) -> None:
    if DEBUG:
        print(f"[debug] {msg}")


def _warn(msg: str) -> None:
    print(f"[warn] {msg}")


REPO_ROOT = Path(__file__).resolve().parents[1]  # repo/tools/ -> repo/
QUERY_DATA_DIR = REPO_ROOT / "src" / "OSSS" / "ai" / "agents" / "query_data"
LC_AGENTS_DIR = REPO_ROOT / "src" / "OSSS" / "ai" / "langchain" / "agents"
HEURISTICS_DIR = REPO_ROOT / "src" / "OSSS" / "ai" / "intents" / "heuristics"
HEURISTICS_INIT = HEURISTICS_DIR / "__init__.py"

ZIP_OUT = REPO_ROOT / "generated_query_data_langchain_agents.zip"


@dataclass
class HandlerSpec:
    mode: str
    keywords: list[str]
    source_label: str
    module_path: str  # python import path for handler module (for forcing import if needed)
    handler_mode: str  # same as mode, kept explicit


def _py_to_module(path: Path) -> str:
    # repo/src/OSSS/... -> OSSS....
    rel = path.relative_to(REPO_ROOT / "src")
    return ".".join(rel.with_suffix("").parts)


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write_text(p: Path, content: str) -> None:
    if DRY_RUN:
        _dbg(f"DRY_RUN: would write {p} ({len(content)} bytes)")
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _is_handler_file(p: Path) -> bool:
    # skip cache / hidden dirs
    if "__pycache__" in p.parts:
        return False

    # ignore private modules
    if p.name.startswith("_"):
        return False

    # ignore known framework files
    if p.name in {
        "__init__.py",
        "query_data_registry.py",
        "query_data_errors.py",
        "query_data_agent.py",
        "query_data_client.py",
        "query_data_dialog.py",
        "query_data_formatters.py",
        "query_data_state.py",
        "query_data_state_store.py",
        "handler_loader.py",
        "agent.py",
        "tools.py",
    }:
        return False

    return p.suffix == ".py"



def _extract_literal_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_literal_str_list(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.List, ast.Tuple)):
        out: list[str] = []
        for elt in node.elts:
            s = _extract_literal_str(elt)
            if s is not None:
                out.append(s)
        return out
    return []


def _summarize_class_attrs(class_node: ast.ClassDef) -> dict[str, str]:
    """
    Debug helper: show if a class defines mode/keywords/source_label.
    """
    out: dict[str, str] = {}
    for stmt in class_node.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1:
            continue
        t = stmt.targets[0]
        if not isinstance(t, ast.Name):
            continue

        if t.id in {"mode", "source_label"}:
            s = _extract_literal_str(stmt.value)
            if s is not None:
                out[t.id] = s
        elif t.id == "keywords":
            kws = _extract_literal_str_list(stmt.value)
            if kws:
                out[t.id] = f"{len(kws)} items"
    return out


def _find_handler_spec(py_file: Path) -> Optional[HandlerSpec]:
    """
    Looks for a class that defines `mode = "<mode>"` and optionally `keywords = [...]`
    and `source_label = "..."`.
    """
    src = _read_text(py_file)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        _warn(f"SyntaxError parsing {py_file}: {e}")
        return None

    class_defs = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if DEBUG_AST:
        _dbg(f"AST classes in {py_file.name}: {[c.name for c in class_defs]}")

    for node in class_defs:
        mode: Optional[str] = None
        keywords: list[str] = []
        source_label: Optional[str] = None

        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1:
                continue
            t = stmt.targets[0]
            if not isinstance(t, ast.Name):
                continue

            if t.id == "mode":
                mode = _extract_literal_str(stmt.value)
            elif t.id == "keywords":
                keywords = _extract_literal_str_list(stmt.value)
            elif t.id == "source_label":
                source_label = _extract_literal_str(stmt.value)

        if mode:
            # defaults
            if not keywords:
                keywords = [mode, mode.replace("_", " ")]
            if not source_label:
                source_label = f"your OSSS data service ({mode})"

            return HandlerSpec(
                mode=mode,
                keywords=keywords,
                source_label=source_label,
                module_path=_py_to_module(py_file),
                handler_mode=mode,
            )

    if DEBUG:
        if class_defs:
            _dbg(f"No handler spec found in {py_file.name}. Class attr summary:")
            for c in class_defs:
                attrs = _summarize_class_attrs(c)
                _dbg(f"  - class {c.name}: {attrs or '(no mode/keywords/source_label literals)'}")
        else:
            _dbg(f"No classes found in {py_file.name}; skipping.")

    return None


def _make_table_py(spec: HandlerSpec) -> str:
    mode = spec.mode
    logger_name = f"OSSS.ai.langchain.{mode}_table"
    model_name = "".join([w.capitalize() for w in mode.split("_")]) + "Filters"

    return f"""# Auto-generated from QueryData handler mode="{mode}"
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("{logger_name}")

SAFE_MAX_ROWS = 200


class {model_name}(BaseModel):
    \"\"\"Optional filters (extend later).\"\"\"
    q: Optional[str] = Field(default=None, description="Optional free-text filter (not applied by default).")


def _coerce_list(payload: Any, *, label: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "{mode}"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning("[%s_table] %s payload dict had no list key. keys=%s", "{mode}", label, list(payload.keys())[:30])
        return []
    logger.warning("[%s_table] %s payload unexpected type=%s", "{mode}", label, type(payload).__name__)
    return []


async def _fetch_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    handler = get_handler("{mode}")
    if handler is None:
        logger.error("[%s_table] No QueryData handler registered for mode=%r", "{mode}", "{mode}")
        return []

    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("{mode}") or []
    return _coerce_list(rows, label="{mode}")


def _build_markdown_table(rows: List[Dict[str, Any]], *, max_rows: int = 50) -> str:
    if not rows:
        return "No records matched your request."

    rows = rows[:max_rows]
    fieldnames = list(rows[0].keys())

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |"
    sep = "| " + " | ".join(["---"] * len(header_cells)) + " |"
    lines = [header, sep]

    for i, r in enumerate(rows, start=1):
        cells = [str(i)]
        for f in fieldnames:
            v = r.get(f, "")
            s = "" if v is None else str(v)
            if len(s) > 120:
                s = s[:117] + "..."
            cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")

    return "\\n".join(lines)


async def run_{mode}_table_structured(
    *,
    filters: Optional[{model_name}],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info("[%s_table] called filters=%s", "{mode}", filters.model_dump() if filters else None)

    rows = await _fetch_rows(skip=skip, limit=limit)
    rows = rows[:SAFE_MAX_ROWS]

    summary = [
        f"I found {{len(rows)}} {mode.replace('_', ' ')} records.",
        "",
        "Sample (first 50):",
        "",
        _build_markdown_table(rows, max_rows=50),
    ]

    return {{
        "reply": "\\n".join(summary),
        "rows": rows,
        "filters": filters.model_dump() if filters else None,
    }}


async def run_{mode}_table_markdown_only(
    *,
    filters: Optional[{model_name}],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_{mode}_table_structured(filters=filters, session_id=session_id, skip=skip, limit=limit)
    return result["reply"]
"""


def _make_table_agent_py(spec: HandlerSpec) -> str:
    mode = spec.mode
    agent_class = "".join([w.capitalize() for w in mode.split("_")]) + "TableAgent"
    tool_fn = f"run_{mode}_table_structured"
    filters_model = "".join([w.capitalize() for w in mode.split("_")]) + "Filters"

    return f"""# Auto-generated LangChain agent for QueryData mode="{mode}"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .{mode}_table import {filters_model}, {tool_fn}

logger = logging.getLogger("OSSS.ai.langchain.agents.{mode}")

class {agent_class}(LangChainAgentProtocol):
    \"\"\"
    LangChain agent that returns a table/listing for `{mode}`.
    \"\"\"

    name = "lc.{mode}_table"
    intent = "{mode}"
    intent_aliases = {spec.keywords!r}

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await {tool_fn}(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent({agent_class}())
"""


def _make_agent_init_py(spec: HandlerSpec) -> str:
    mode = spec.mode
    agent_class = "".join([w.capitalize() for w in mode.split("_")]) + "TableAgent"
    return f"""from __future__ import annotations

# Import side-effect registers the agent
from .{mode}_table_agent import {agent_class}  # noqa: F401
"""


def _make_heuristics_rules_py(spec: HandlerSpec) -> str:
    mode = spec.mode
    kw = list(dict.fromkeys([f"show {mode.replace('_',' ')}", mode, *spec.keywords]))
    rule_name = f"{mode}__explicit_show"

    return f"""from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name={rule_name!r},
        intent={mode!r},
        priority=55,
        keywords={kw!r},
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={{"source": "{mode}_rules"}},
    ),
]
"""


def _ensure_heuristics_init_import(mode: str) -> None:
    if not HEURISTICS_INIT.exists():
        _dbg(f"heuristics __init__.py not found at {HEURISTICS_INIT}; skipping hook")
        return

    text = _read_text(HEURISTICS_INIT)
    import_line = f"from .{mode}_rules import RULES as {mode.upper()}_RULES\n"
    if import_line in text:
        _dbg(f"heuristics init already imports {mode}_rules")
        return

    text2 = text + ("" if text.endswith("\n") else "\n") + import_line

    if "ALL_RULES" in text2:
        text2 = re.sub(
            r"(ALL_RULES\s*=\s*\[)([^\]]*)\]",
            lambda m: m.group(0)
            if f"{mode.upper()}_RULES" in m.group(0)
            else f"{m.group(1)}{m.group(2)}    *{mode.upper()}_RULES,\n]",
            text2,
            count=1,
            flags=re.DOTALL,
        )

    _dbg(f"Updating heuristics __init__.py to include {mode}_rules import")
    _write_text(HEURISTICS_INIT, text2)


def main() -> int:
    print("---- generator debug ----")
    print(f"REPO_ROOT      = {REPO_ROOT}")
    print(f"QUERY_DATA_DIR = {QUERY_DATA_DIR}")
    print(f"LC_AGENTS_DIR  = {LC_AGENTS_DIR}")
    print(f"HEURISTICS_DIR = {HEURISTICS_DIR}")
    print(f"HEURISTICS_INIT= {HEURISTICS_INIT}")
    print(f"ZIP_OUT        = {ZIP_OUT}")
    print(f"DEBUG={DEBUG} DEBUG_AST={DEBUG_AST} DRY_RUN={DRY_RUN}")
    print("------------------------")

    if not QUERY_DATA_DIR.exists():
        print(f"ERROR: not found: {QUERY_DATA_DIR}")
        return 2


    all_py = sorted(QUERY_DATA_DIR.rglob("*.py"))

    print(f"[scan] rglob found {len(all_py)} .py files under {QUERY_DATA_DIR}")
    if DEBUG:
        for p in all_py[:50]:
            _dbg(f"  - {p.relative_to(QUERY_DATA_DIR)}")

    for py in all_py:
        if not _is_handler_file(py):
            continue

    created_files: list[Path] = []
    processed = 0
    skipped_non_handler = 0
    skipped_no_spec = 0
    matched_specs = 0

    for py in all_py:
        if not _is_handler_file(py):
            skipped_non_handler += 1
            _dbg(f"skip (not handler file): {py.name}")
            continue

        processed += 1
        _dbg(f"process: {py.name}")

        spec = _find_handler_spec(py)
        if not spec:
            skipped_no_spec += 1
            _dbg(f"  -> no HandlerSpec extracted (no class with literal mode=...)")
            continue

        matched_specs += 1
        _dbg(f"  -> found HandlerSpec: mode={spec.mode!r} keywords={len(spec.keywords)} module={spec.module_path}")

        agent_dir = LC_AGENTS_DIR / spec.mode
        table_py = agent_dir / f"{spec.mode}_table.py"
        agent_py = agent_dir / f"{spec.mode}_table_agent.py"
        init_py = agent_dir / "__init__.py"
        rules_py = HEURISTICS_DIR / f"{spec.mode}_rules.py"

        for path, content in [
            (table_py, _make_table_py(spec)),
            (agent_py, _make_table_agent_py(spec)),
            (init_py, _make_agent_init_py(spec)),
            (rules_py, _make_heuristics_rules_py(spec)),
        ]:
            if path.exists():
                try:
                    existing = _read_text(path)
                except Exception as e:
                    _warn(f"Failed reading existing {path}: {e}")
                    existing = None
                if existing is not None and existing == content:
                    _dbg(f"  unchanged: {path.relative_to(REPO_ROOT)}")
                    continue
                _dbg(f"  will write (changed): {path.relative_to(REPO_ROOT)}")
            else:
                _dbg(f"  will write (new): {path.relative_to(REPO_ROOT)}")

            _write_text(path, content)
            created_files.append(path)

        _ensure_heuristics_init_import(spec.mode)

    print("---- summary ----")
    print(f"processed handler-candidate files: {processed}")
    print(f"skipped (non-handler):            {skipped_non_handler}")
    print(f"skipped (no spec):                {skipped_no_spec}")
    print(f"matched HandlerSpec:              {matched_specs}")
    print(f"files created/changed:            {len(created_files)}")
    print("-----------------")

    if not created_files:
        print("No files created/changed (nothing to do).")
        _warn(
            "If you expected handlers in subfolders, this script currently only scans query_data/*.py.\n"
            "Try changing QUERY_DATA_DIR.glob('*.py') to QUERY_DATA_DIR.rglob('*.py') if needed."
        )
        return 0

    if ZIP_OUT.exists() and not DRY_RUN:
        ZIP_OUT.unlink()

    if not DRY_RUN:
        with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in created_files:
                arc = p.relative_to(REPO_ROOT)
                z.write(p, arcname=str(arc))

        print(f"Created/updated {len(created_files)} files.")
        print(f"Wrote zip: {ZIP_OUT}")
    else:
        print(f"DRY_RUN: would have zipped {len(created_files)} files to {ZIP_OUT}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
