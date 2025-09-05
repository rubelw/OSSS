#!/usr/bin/env python3
"""
Add created_at / updated_at columns to specific SQLAlchemy models.

- It targets files in src/OSSS/db/models matching the names you listed.
- If a file already contains created_at/updated_at, it is skipped.
- It injects the columns right after __tablename__ = "..." (or after the class header if __tablename__ missing).
- It ensures the sqlalchemy imports needed are present.

If your project already has a TimestampMixin you prefer to use, you can
toggle USE_MIXIN = True and it will try to add TimestampMixin to the class
bases + import it (fallbacks to raw columns if it can’t find an import spot).
"""

from __future__ import annotations
import re
from pathlib import Path

ROOT = Path("../src/OSSS/db/models")

TARGET_MODULES = [
    "agenda_item_files.py",
    "alignments.py",
    "asset_parts.py",
    "catalog_items.py",
    "committees.py",
    "degree_task_map.py",
    "diagram_elements.py",
    "document_activity.py",
    "document_notifications.py",
    "document_permissions.py",
    "document_search_index.py",
    "journal_batches.py",
    "journal_entries.py",
    "materials.py",
    "models.py",
    "stacks.py",
    "standards.py",
    "unit_standard_map.py",
]

USE_MIXIN = False  # set True if you want to add TimestampMixin instead of raw columns

# ---------- helpers ----------

CLASS_RE = re.compile(r"^class\s+\w+\s*\((?P<bases>[^)]*)\)\s*:\s*$", re.M)
TABLENAME_RE = re.compile(r'^\s*__tablename__\s*=\s*["\']([^"\']+)["\']\s*$', re.M)
HAS_CREATED_RE = re.compile(r"^\s*created_at\s*=", re.M)
HAS_UPDATED_RE = re.compile(r"^\s*updated_at\s*=", re.M)

def ensure_sa_imports(text: str) -> str:
    """Ensure we have 'from sqlalchemy import Column, DateTime, func'."""
    needed = {"Column", "DateTime", "func"}
    # Try to merge into existing 'from sqlalchemy import ...'
    m = re.search(r"^from\s+sqlalchemy\s+import\s+([^\n]+)$", text, re.M)
    if m:
        names = {n.strip() for n in m.group(1).split(",")}
        missing = needed - names
        if missing:
            new_line = "from sqlalchemy import " + ", ".join(sorted(names | needed))
            text = text[:m.start()] + new_line + text[m.end():]
        return text
    # Else inject a fresh import after the shebang / future import / first import block
    insert_at = 0
    # keep any module docstring / __future__ imports at the very top
    for m2 in re.finditer(r"^(?:from\s+__future__\s+import.*|#.*|\"\"\".*?\"\"\"|\'\'\'.*?\'\'\')\s*$", text, re.M | re.S):
        insert_at = max(insert_at, m2.end())
    snippet = "\nfrom sqlalchemy import Column, DateTime, func\n"
    return text[:insert_at] + snippet + text[insert_at:]

def add_timestamp_mixin_import(text: str) -> str:
    """
    Try to add TimestampMixin to an existing mixin import line.
    Common variants:
      from .mixins import UUIDMixin, TimestampMixin
      from OSSS.db.models.mixins import UUIDMixin
    """
    patterns = [
        r"^from\s+\.\s*mixins\s+import\s+([^\n]+)$",
        r"^from\s+OSSS\.db\.models\.mixins\s+import\s+([^\n]+)$",
        r"^from\s+\.\s*_mixins\s+import\s+([^\n]+)$",
        r"^from\s+OSSS\.db\.models\._mixins\s+import\s+([^\n]+)$",
    ]
    for p in patterns:
        m = re.search(p, text, re.M)
        if m:
            names = {n.strip() for n in m.group(1).split(",")}
            if "TimestampMixin" not in names:
                names.add("TimestampMixin")
                new_line = re.sub(p, lambda _: m.group(0).split("import")[0] + "import " + ", ".join(sorted(names)), text, count=1, flags=re.M)
                return new_line
            return text
    # No existing import found → we’ll fall back to raw columns later
    return text

def inject_mixin_into_class_bases(text: str) -> tuple[str, bool]:
    """
    Insert TimestampMixin in the first class bases that includes 'Base'.
    Returns (new_text, changed_flag).
    """
    for m in CLASS_RE.finditer(text):
        bases = m.group("bases")
        if "Base" not in bases:
            continue
        if "TimestampMixin" in bases:
            return text, False
        new_bases = bases.strip()
        if new_bases:
            new_bases = "TimestampMixin, " + new_bases
        else:
            new_bases = "TimestampMixin"
        new_header = m.group(0).replace(bases, new_bases)
        text = text[:m.start()] + new_header + text[m.end():]
        return text, True
    return text, False

RAW_COLUMNS_SNIPPET = """
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
"""

def inject_raw_columns(text: str) -> str:
    # Avoid duplicate insertion
    if HAS_CREATED_RE.search(text) or HAS_UPDATED_RE.search(text):
        return text
    # Prefer to inject after __tablename__
    m = TABLENAME_RE.search(text)
    if m:
        insert_pos = m.end()
        return text[:insert_pos] + RAW_COLUMNS_SNIPPET + text[insert_pos:]
    # Else inject just after the first class header
    m2 = CLASS_RE.search(text)
    if m2:
        insert_pos = m2.end()
        return text[:insert_pos] + RAW_COLUMNS_SNIPPET + text[insert_pos:]
    return text  # no class? leave as-is

def process_file(path: Path) -> tuple[bool, str]:
    original = path.read_text(encoding="utf-8")
    text = original

    # Skip if already has both columns
    if HAS_CREATED_RE.search(text) and HAS_UPDATED_RE.search(text):
        return False, "already has created_at/updated_at"

    text = ensure_sa_imports(text)

    if USE_MIXIN:
        before = text
        text = add_timestamp_mixin_import(text)
        text, mixed = inject_mixin_into_class_bases(text)
        if not mixed:
            # fallback to raw columns if we couldn't add the mixin
            text = inject_raw_columns(text)
            note = "added raw columns (mixin not found)"
        else:
            note = "added TimestampMixin"
        changed = text != original
        if changed:
            path.write_text(text, encoding="utf-8")
        return changed, note

    # default: inject raw columns
    text = inject_raw_columns(text)
    changed = text != original
    if changed:
        path.write_text(text, encoding="utf-8")
        return True, "added raw columns"
    return False, "no changes"

def main():
    base = ROOT
    if not base.exists():
        print(f"!! Path not found: {base}")
        return

    changed_any = False
    for name in TARGET_MODULES:
        file_path = base / name
        if not file_path.exists():
            print(f"- skip (missing): {file_path}")
            continue
        changed, msg = process_file(file_path)
        print(f"* {file_path}: {msg}")
        changed_any = changed_any or changed

    if not changed_any:
        print("No files changed.")

if __name__ == "__main__":
    main()
