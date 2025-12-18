#!/usr/bin/env python3
from __future__ import annotations

import ast
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

LOG = logging.getLogger("generate_data_views_ast")

def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(handler)

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDLERS_DIR = REPO_ROOT / "src" / "OSSS" / "ai" / "agents" / "query_data" / "handlers"

BASE_URL = "http://host.containers.internal:8081"
DEFAULT_SKIP = 0
DEFAULT_LIMIT = 50
DEFAULT_MAX_ROWS = 200


@dataclass
class HandlerInfo:
    name: str
    description: str
    path: str
    skip: int
    limit: int


def _lit(node: ast.AST, *, context: str = "") -> Optional[Any]:
    try:
        val = ast.literal_eval(node)
        LOG.debug("literal_eval OK (%s): %r", context, val)
        return val
    except Exception as e:
        LOG.debug("literal_eval FAIL (%s): %s | node=%s", context, e, ast.dump(node, include_attributes=False))
        return None


def _first_sentence(doc: str) -> str:
    doc = (doc or "").strip()
    if not doc:
        return ""
    first = doc.splitlines()[0].strip()
    LOG.debug("docstring first line: %r", first)
    return first


def extract_from_file(pyfile: Path) -> Optional[HandlerInfo]:
    LOG.info("Processing file: %s", pyfile)

    try:
        src = pyfile.read_text(encoding="utf-8")
        LOG.debug("Read %d chars from %s", len(src), pyfile.name)
    except Exception as e:
        LOG.exception("Failed reading %s: %s", pyfile, e)
        return None

    try:
        tree = ast.parse(src, filename=str(pyfile))
        LOG.debug("Parsed AST OK: %s", pyfile.name)
    except SyntaxError as e:
        LOG.error("SyntaxError parsing %s: %s", pyfile.name, e)
        return None
    except Exception as e:
        LOG.exception("Unexpected error parsing %s: %s", pyfile.name, e)
        return None

    class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    LOG.debug("Found %d class defs in %s", len(class_nodes), pyfile.name)
    if not class_nodes:
        LOG.warning("No classes found in %s; skipping", pyfile.name)
        return None

    cls = next((c for c in class_nodes if c.name.endswith("Handler")), class_nodes[0])
    LOG.info("Selected class: %s (from %s)", cls.name, pyfile.name)

    mode: Optional[str] = None
    endpoint: Optional[str] = None
    description = _first_sentence(ast.get_docstring(cls) or "")

    default_skip = DEFAULT_SKIP
    default_limit = DEFAULT_LIMIT

    LOG.debug(
        "Initial defaults for %s: mode=%r endpoint=%r description=%r skip=%r limit=%r",
        cls.name, mode, endpoint, description, default_skip, default_limit
    )

    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            key = stmt.targets[0].id
            LOG.debug("Found class assignment: %s = <expr>", key)
            val = _lit(stmt.value, context=f"{pyfile.name}:{cls.name}.{key}")

            if key == "mode" and isinstance(val, str):
                mode = val
                LOG.info("Extracted mode=%r from %s.%s", mode, cls.name, key)

            elif key in ("endpoint", "path", "route") and isinstance(val, str):
                endpoint = val
                LOG.info("Extracted endpoint/path=%r from %s.%s", endpoint, cls.name, key)

            elif key == "description" and isinstance(val, str):
                description = val.strip()
                LOG.info("Extracted description from %s.%s: %r", cls.name, key, description)

            elif key == "default_skip" and isinstance(val, int):
                default_skip = val
                LOG.info("Extracted default_skip=%d from %s.%s", default_skip, cls.name, key)

            elif key == "default_limit" and isinstance(val, int):
                default_limit = val
                LOG.info("Extracted default_limit=%d from %s.%s", default_limit, cls.name, key)

    name = mode or cls.name.removesuffix("Handler").lower()
    LOG.info("Computed name=%r (mode=%r, class=%s)", name, mode, cls.name)

    # ✅ NEW: derive endpoint from mode
    if not endpoint:
        if mode:
            endpoint = f"/api/{mode}"
            LOG.warning(
                "No endpoint/path/route literal found for %s in %s. "
                "FALLING BACK to derived endpoint=%r from mode=%r",
                cls.name, pyfile.name, endpoint, mode
            )
        else:
            LOG.warning(
                "No endpoint/path/route found AND no mode found for %s in %s; skipping.",
                cls.name, pyfile.name
            )
            return None

    if not description:
        description = name.replace("_", " ").title()
        LOG.debug("Filled empty description with title-case: %r", description)

    info = HandlerInfo(
        name=name,
        description=description,
        path=endpoint,
        skip=default_skip,
        limit=default_limit,
    )
    LOG.info("Extracted HandlerInfo: %r", info)
    return info


def emit(infos: list[HandlerInfo]) -> None:
    LOG.info("Emitting DATA_VIEWS for %d handlers", len(infos))

    print("from __future__ import annotations")
    print("")
    print("from .specs import DataViewSpec")
    print("")
    print("DATA_VIEWS: dict[str, DataViewSpec] = {")
    for i in sorted(infos, key=lambda x: x.name):
        LOG.debug("Emitting spec for %s -> %s", i.name, i.path)
        print(f'    "{i.name}": DataViewSpec(')
        print(f'        name="{i.name}",')
        print(f'        description="{i.description}",')
        print('        source="http_get",')
        print(f'        base_url="{BASE_URL}",')
        print(f'        path="{i.path}",')
        print(f"        default_query_params={{'skip': {i.skip}, 'limit': {i.limit}}},")
        print(f'        store_key="{i.name}_result",')
        print(f"        max_rows={DEFAULT_MAX_ROWS},")
        print("    ),")
    print("}")
    print("")


def main() -> None:
    configure_logging()
    LOG.info("Starting generator")
    LOG.debug("REPO_ROOT=%s", REPO_ROOT)
    LOG.debug("HANDLERS_DIR=%s", HANDLERS_DIR)

    if not HANDLERS_DIR.exists():
        LOG.error("Handlers dir not found: %s", HANDLERS_DIR)
        raise SystemExit(f"Handlers dir not found: {HANDLERS_DIR}")

    infos: list[HandlerInfo] = []
    skipped: list[str] = []

    handler_files = sorted(HANDLERS_DIR.glob("*.py"))
    LOG.info("Discovered %d .py files in handlers dir", len(handler_files))

    for pyfile in handler_files:
        if pyfile.name.startswith("_"):
            LOG.debug("Skipping private file: %s", pyfile.name)
            continue

        info = extract_from_file(pyfile)
        if info is None:
            skipped.append(pyfile.name)
            LOG.warning("SKIP: %s (could not infer spec)", pyfile.name)
        else:
            infos.append(info)
            LOG.info("OK: %s -> view=%s path=%s", pyfile.name, info.name, info.path)

    emit(infos)

    if skipped:
        LOG.warning("Skipped %d files", len(skipped))
        print("# ---- Skipped (could not statically infer mode/endpoint) ----")
        for s in skipped:
            print(f"# {s}")

    LOG.info("Done. Extracted %d specs; skipped %d files.", len(infos), len(skipped))


if __name__ == "__main__":
    main()
