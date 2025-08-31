#!/usr/bin/env python3
"""
List rows from the `document_versions` table (joining `documents` and `files`)
using a local Postgres by default.

Default connection (can be overridden):
  user=osss password=password host=localhost port=5433 db=osss (async via asyncpg)
"""

import os
import csv
import argparse
import asyncio
from typing import List, Tuple, Dict

from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Order-by options exposed to the CLI (safe, mapped to real columns)
SAFE_ORDER_MAP: Dict[str, str] = {
    "created_at":   "dv.created_at",
    "published_at": "dv.published_at",
    "version_no":   "dv.version_no",
    "title":        "d.title",
    "filename":     "f.filename",
}
SAFE_ORDER_COLS = set(SAFE_ORDER_MAP.keys())

QUERY_PRIMARY = """
SELECT
  dv.id,
  d.id               AS document_id,
  d.title            AS doc_title,
  dv.version_no,
  f.id               AS file_id,
  f.filename         AS file_name,
  f.storage_key,
  dv.checksum,
  dv.created_by,
  dv.created_at,
  dv.published_at
FROM document_versions dv
JOIN documents d ON d.id = dv.document_id
JOIN files f     ON f.id = dv.file_id
{where}
ORDER BY {order_col} {order_dir}
LIMIT :limit OFFSET :offset
"""

QUERY_FALLBACK = """
SELECT
  dv.id,
  dv.document_id,
  dv.version_no,
  dv.file_id,
  dv.created_at,
  dv.published_at
FROM document_versions dv
{where}
ORDER BY {order_col} {order_dir}
LIMIT :limit OFFSET :offset
"""

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="List rows from document_versions (with joins to documents/files).")
    p.add_argument("--dsn", help="Full SQLAlchemy URL; overrides other connection flags")
    p.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5433")))
    p.add_argument("--db",   default=os.getenv("PGDATABASE", "osss"))
    p.add_argument("--user", default=os.getenv("PGUSER", "osss"))
    p.add_argument("--password", default=os.getenv("PGPASSWORD", "password"))
    p.add_argument("--sync", action="store_true", help="Use sync driver (psycopg2/pg8000) instead of asyncpg")

    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)

    p.add_argument("--like-title", help="Case-insensitive substring match on documents.title")
    p.add_argument("--like-file",  help="Case-insensitive substring match on files.filename")
    p.add_argument("--document",   help="Exact document title (case-insensitive)")
    p.add_argument("--published-only", action="store_true", help="Only rows where published_at IS NOT NULL")

    p.add_argument("--order-by", default="created_at", choices=sorted(SAFE_ORDER_COLS))
    p.add_argument("--asc", action="store_true", help="Ascending order (default desc)")

    p.add_argument("--csv", help="Write results to CSV file")
    return p.parse_args()

def build_dsn(args: argparse.Namespace) -> tuple[str, bool]:
    env_dsn = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if args.dsn:
        return args.dsn, ("+asyncpg" in args.dsn or args.dsn.startswith("postgresql+asyncpg"))
    if env_dsn:
        return env_dsn, ("+asyncpg" in env_dsn or env_dsn.startswith("postgresql+asyncpg"))
    if args.sync:
        dsn = f"postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
        return dsn, False
    else:
        dsn = f"postgresql+asyncpg://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
        return dsn, True

def build_where(args: argparse.Namespace) -> Tuple[str, dict]:
    clauses = []
    binds = {}
    if args.like_title:
        clauses.append("d.title ILIKE :like_title")
        binds["like_title"] = f"%{args.like_title}%"
    if args.like_file:
        clauses.append("f.filename ILIKE :like_file")
        binds["like_file"] = f"%{args.like_file}%"
    if args.document:
        clauses.append("lower(d.title) = lower(:doc_exact)")
        binds["doc_exact"] = args.document
    if args.published_only:
        clauses.append("dv.published_at IS NOT NULL")

    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where, binds

def render_table(rows: List[dict]):
    if not rows:
        print("(no rows)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    sep = " | "
    print(sep.join(c.ljust(widths[c]) for c in cols))
    print(sep.join("-" * widths[c] for c in cols))
    for r in rows:
        print(sep.join(str(r.get(c, "")).ljust(widths[c]) for c in cols))

async def run_async(dsn: str, args: argparse.Namespace):
    engine: AsyncEngine = create_async_engine(dsn, future=True)
    where, binds = build_where(args)
    order_sql = SAFE_ORDER_MAP.get(args.order_by, SAFE_ORDER_MAP["created_at"])
    order_dir = "ASC" if args.asc else "DESC"
    q = QUERY_PRIMARY.format(where=where, order_col=order_sql, order_dir=order_dir)
    fb = QUERY_FALLBACK.format(where=where, order_col="dv.created_at", order_dir=order_dir)

    rows: list[dict] = []
    async with engine.begin() as conn:
        try:
            res = await conn.execute(text(q), {"limit": args.limit, "offset": args.offset, **binds})
            rows = [dict(r._mapping) for r in res.fetchall()]
        except Exception:
            res = await conn.execute(text(fb), {"limit": args.limit, "offset": args.offset, **binds})
            rows = [dict(r._mapping) for r in res.fetchall()]
    await engine.dispose()
    output(rows, args)

def run_sync(dsn: str, args: argparse.Namespace):
    engine = create_engine(dsn, future=True)
    where, binds = build_where(args)
    order_sql = SAFE_ORDER_MAP.get(args.order_by, SAFE_ORDER_MAP["created_at"])
    order_dir = "ASC" if args.asc else "DESC"
    q = QUERY_PRIMARY.format(where=where, order_col=order_sql, order_dir=order_dir)
    fb = QUERY_FALLBACK.format(where=where, order_col="dv.created_at", order_dir=order_dir)

    rows: list[dict] = []
    with engine.begin() as conn:
        try:
            res = conn.execute(text(q), {"limit": args.limit, "offset": args.offset, **binds})
            rows = [dict(r._mapping) for r in res.fetchall()]
        except Exception:
            res = conn.execute(text(fb), {"limit": args.limit, "offset": args.offset, **binds})
            rows = [dict(r._mapping) for r in res.fetchall()]
    engine.dispose()
    output(rows, args)

def output(rows: list[dict], args: argparse.Namespace):
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            else:
                writer = csv.writer(f)
                writer.writerow(["(no rows)"])
        print(f"Wrote {len(rows)} rows to {args.csv}")
    else:
        render_table(rows)

def main():
    args = parse_args()
    dsn, is_async = build_dsn(args)
    if is_async:
        asyncio.run(run_async(dsn, args))
    else:
        run_sync(dsn, args)

if __name__ == "__main__":
    main()
