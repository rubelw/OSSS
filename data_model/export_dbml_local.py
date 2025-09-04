#!/usr/bin/env python3
import argparse
import importlib
import logging
import os
import pkgutil
import sys
from typing import Optional

import sqlalchemy as sa

# ---------------------------
# CLI
# ---------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Export DBML from local SQLAlchemy models (FastAPI project)."
    )
    default_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    parser.add_argument("--src-root", default=default_src, help="Path that contains the 'OSSS' package (default: ../src)")
    parser.add_argument("--models-package", default="OSSS.db.models", help="Dotted package path to your models (default: OSSS.db.models)")
    parser.add_argument("--output", default="schema.dbml", help="Output DBML filename")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logs")
    return parser.parse_args()


# ---------------------------
# Import helpers
# ---------------------------

def import_all_models(root_pkg: str) -> None:
    """
    Import all modules under the given package so that all model classes register
    themselves on their SQLAlchemy Base.metadata.
    """
    pkg = importlib.import_module(root_pkg)
    pkg_path = getattr(pkg, "__path__", None)
    if not pkg_path:
        return

    prefix = pkg.__name__ + "."
    for modinfo in pkgutil.walk_packages(pkg_path, prefix=prefix):
        fullname = modinfo.name
        # Skip private or tests/migrations-like modules
        parts = fullname.split(".")
        if any(p.startswith("_") for p in parts):
            continue
        if any(p in {"tests", "migrations"} for p in parts):
            continue

        try:
            importlib.import_module(fullname)
            logging.getLogger(__name__).debug("Imported %s", fullname)
        except Exception as exc:
            logging.getLogger(__name__).warning("Skipping %s due to import error: %s", fullname, exc)


# ---------------------------
# DBML helpers
# ---------------------------

def _compile_type(coltype: sa.types.TypeEngine) -> str:
    """Map SQLAlchemy types to DBML-ish names. Fallback to str(coltype)."""
    t = coltype
    # Common types
    if isinstance(t, sa.String):
        if getattr(t, "length", None):
            return f"varchar({t.length})"
        return "text"
    if isinstance(t, sa.Text):
        return "text"
    if isinstance(t, sa.Integer):
        return "int"
    if isinstance(t, sa.BigInteger):
        return "bigint"
    if isinstance(t, sa.SmallInteger):
        return "smallint"
    if isinstance(t, sa.Numeric):
        if getattr(t, "precision", None) is not None and getattr(t, "scale", None) is not None:
            return f"numeric({t.precision},{t.scale})"
        return "numeric"
    if isinstance(t, sa.Float):
        return "float"
    if isinstance(t, sa.Boolean):
        return "boolean"
    if isinstance(t, sa.Date):
        return "date"
    if isinstance(t, sa.DateTime) or isinstance(t, sa.types.TIMESTAMP):
        return "timestamp"
    if isinstance(t, sa.types.UUID):
        return "uuid"
    # Dialect-specific or custom
    try:
        from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, JSON, INET
        if isinstance(t, PGUUID):
            return "uuid"
        if isinstance(t, JSONB):
            return "jsonb"
        if isinstance(t, JSON):
            return "json"
        if isinstance(t, INET):
            return "inet"
    except Exception:
        pass
    if isinstance(t, sa.JSON):
        return "json"
    # Fallback
    return str(t)


def _default_to_str(col: sa.Column) -> Optional[str]:
    # Column default (client side)
    if col.default is not None:
        try:
            if col.default.is_scalar:
                return repr(col.default.arg)
        except Exception:
            pass
    # Server default
    if col.server_default is not None:
        try:
            # Often a SQL ClauseElement/TextClause
            return str(getattr(col.server_default.arg, "text", col.server_default.arg))
        except Exception:
            return str(col.server_default)
    return None


def emit_table_dbml(table: sa.Table) -> str:
    """Emit a DBML block for a single Table."""
    name = table.name
    schema = table.schema
    fq_name = f"{schema}.{name}" if schema else name

    lines = [f"Table {fq_name} {{"]

    # Columns
    for col in table.columns:
        parts = [f"  {col.name} {_compile_type(col.type)}"]
        attrs = []
        if col.primary_key:
            attrs.append("pk")
        if not col.nullable:
            attrs.append("not null")
        if col.unique:
            attrs.append("unique")
        dflt = _default_to_str(col)
        if dflt is not None:
            # escape braces/quotes lightly
            dflt_clean = str(dflt).replace("{", "\{").replace("}", "\}")
            attrs.append(f'default: "{dflt_clean}"')
        if getattr(col, "autoincrement", False):
            attrs.append("increment")
        if attrs:
            parts.append(f"[{', '.join(attrs)}]")
        lines.append(" ".join(parts))

    # Indexes (simple)
    if table.indexes:
        lines.append("")
        lines.append("  Indexes {")
        for idx in sorted(table.indexes, key=lambda i: i.name or ""):
            cols = ", ".join(getattr(c, "name", str(c)) for c in idx.expressions)
            flags = []
            if idx.unique:
                flags.append("unique")
            idx_name = f' name: "{idx.name}"' if idx.name else ""
            flag_str = f" [{', '.join(flags)}{(',' if flags and idx_name else '')}{idx_name.strip()}]" if (flags or idx_name) else ""
            lines.append(f"    ({cols}){flag_str}")
        lines.append("  }")

    # Unique constraints (composite)
    uniques = [
        c for c in table.constraints
        if isinstance(c, sa.UniqueConstraint) and len(c.columns) > 1
    ]
    if uniques:
        lines.append("")
        lines.append("  Indexes {")
        for uc in uniques:
            cols = ", ".join(col.name for col in uc.columns)
            uc_name = f' name: "{uc.name}"' if uc.name else ""
            lines.append(f"    ({cols}) [unique{(',' if uc_name else '')}{uc_name}]")
        lines.append("  }")

    lines.append("}")
    return "\n".join(lines)


def emit_refs_dbml(metadata: sa.MetaData) -> str:
    """Emit DBML Ref lines for all foreign keys in metadata."""
    out = []
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            src = f"{table.schema + '.' if table.schema else ''}{table.name}.{fk.parent.name}"
            reft = fk.column.table
            tgt = f"{reft.schema + '.' if reft.schema else ''}{reft.name}.{fk.column.name}"
            opts = []
            ondelete = getattr(fk.constraint, "ondelete", None)
            onupdate = getattr(fk.constraint, "onupdate", None)
            if ondelete:
                opts.append(f"delete: {ondelete}")
            if onupdate:
                opts.append(f"update: {onupdate}")
            opt_str = f" [{', '.join(opts)}]" if opts else ""
            out.append(f"Ref: {src} > {tgt}{opt_str}")
    return "\n".join(out)


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    # Ensure local src-root is importable
    if not os.path.isdir(args.src_root):
        raise SystemExit(f"--src-root not found: {args.src_root}")
    if args.src_root not in sys.path:
        sys.path.insert(0, args.src_root)
        logging.debug("Added to sys.path: %s", args.src_root)

    # Import all model modules
    logging.info("Importing models from %s ...", args.models_package)
    import_all_models(args.models_package)

    # Import the Base that models registered on
    try:
        base_mod = importlib.import_module("OSSS.db.base")
        Base = getattr(base_mod, "Base")
    except Exception as exc:
        raise SystemExit(f"Could not import OSSS.db.base: {exc}")

    md: sa.MetaData = Base.metadata

    # Build DBML
    chunks = []
    # Sort tables for stable output
    for tname in sorted(md.tables.keys()):
        table = md.tables[tname]
        chunks.append(emit_table_dbml(table))

    # Refs last
    chunks.append("")
    chunks.append(emit_refs_dbml(md))

    dbml = "\n\n".join(chunks).strip() + "\n"

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(dbml)

    logging.info("Wrote DBML to %s (%d tables)", args.output, len(md.tables))


if __name__ == "__main__":
    main()

def emit_table_dbml(table) -> str:
    """Emit a single Table {...} block in DBML, including table/column notes."""
    lines = []
    schema_prefix = f"{table.schema}." if getattr(table, "schema", None) and table.schema != "public" else ""
    lines.append(f"Table {schema_prefix}{table.name} {{")

    # Columns
    for col in table.columns:
        parts = [f"  {col.name} {_compile_type(col.type)}"]
        attrs = []
        if col.primary_key:
            attrs.append("pk")
        if not col.nullable:
            attrs.append("not null")
        if col.unique:
            attrs.append("unique")

        dflt = _default_to_str(col)
        if dflt is not None:
            # keep whatever quoting _default_to_str returns
            attrs.append(f"default: {dflt}")

        # Column note from SQLAlchemy (comment, info['note'], or doc)
        c_note = getattr(col, 'comment', None) or getattr(col, 'doc', None)
        try:
            info_note = getattr(col, 'info', {}).get('note')
        except Exception:
            info_note = None
        if not c_note and info_note:
            c_note = info_note
        if c_note:
            note_clean = str(c_note).replace('\\', '\\\\').replace("'", "\\'").replace("\n", " | ")
            attrs.append(f"note: '{note_clean}'")

        if attrs:
            parts.append(f"[{', '.join(attrs)}]")
        lines.append(" ".join(parts))

    # Table-level note (multi-line)
    t_note = getattr(table, 'comment', None)
    try:
        t_info_note = getattr(table, 'info', {}).get('note')
    except Exception:
        t_info_note = None
    if not t_note and t_info_note:
        t_note = t_info_note
    if t_note:
        lines.append("")
        lines.append("  Note: '''")
        for ln in str(t_note).splitlines():
            lines.append(f"  {ln}")
        lines.append("  '''")

    # Indexes (simple)
    if table.indexes:
        lines.append("")
        lines.append("  Indexes {")
        for idx in sorted(table.indexes, key=lambda i: i.name or ""):
            cols = ", ".join(c.name for c in idx.columns)
            uniq = " [unique]" if idx.unique else ""
            lines.append(f"    ({cols}){uniq}")
        lines.append("  }")

    lines.append("}")
    return "\n".join(lines)
