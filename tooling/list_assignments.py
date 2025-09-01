#!/usr/bin/env python3
"""
List rows from the `files` table using a local Postgres by default.

Default connection (can be overridden):
  user=osss password=password host=localhost port=5433 db=osss (async via asyncpg)

Examples:
  python list_files.py                        # uses defaults above
  python list_files.py --sync                 # use psycopg2/pg8000 sync driver
  python list_files.py --db mydb --user me --password secret
  python list_files.py --limit 20 --like ".pdf" --order-by filename --asc
  python list_files.py --csv files_dump.csv

You can also pass a full DSN to override everything:
  python list_files.py --dsn postgresql+asyncpg://user:pass@localhost:5432/dbname
  DATABASE_URL=postgresql://user:pass@localhost:5432/db python list_files.py
"""

import os
import sys
import csv
import argparse
import asyncio
from typing import List, Tuple

from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

SAFE_ORDER_COLS = {"created_at", "updated_at", "filename", "size"}

QUERY_PRIMARY = """
SELECT *
FROM assignments
{where}
ORDER BY {order_col} {order_dir}
LIMIT :limit OFFSET :offset
"""

QUERY_FALLBACK = """
SELECT id, filename, storage_key
FROM files
{where}
ORDER BY {order_col} {order_dir}
LIMIT :limit OFFSET :offset
"""

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="List rows from files table (defaults to local Postgres)")
    p.add_argument("--dsn", help="Full SQLAlchemy URL; overrides other connection flags")
    p.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5433")))
    p.add_argument("--db",   default=os.getenv("PGDATABASE", "osss"))
    p.add_argument("--user", default=os.getenv("PGUSER", "osss"))
    p.add_argument("--password", default=os.getenv("PGPASSWORD", "password"))
    p.add_argument("--sync", action="store_true", help="Use sync driver (psycopg2/pg8000) instead of asyncpg")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--like", help="Case-insensitive substring match on filename")
    p.add_argument("--order-by", default="created_at", choices=sorted(SAFE_ORDER_COLS))
    p.add_argument("--asc", action="store_true", help="Ascending order (default desc)")
    p.add_argument("--csv", help="Write results to CSV file")
    return p.parse_args()

def build_dsn(args: argparse.Namespace) -> tuple[str, bool]:
    # if explicit DSN provided or env DATABASE_URL/DB_URL set, use that
    env_dsn = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if args.dsn:
        return args.dsn, ("+asyncpg" in args.dsn or args.dsn.startswith("postgresql+asyncpg"))
    if env_dsn:
        return env_dsn, ("+asyncpg" in env_dsn or env_dsn.startswith("postgresql+asyncpg"))
    # otherwise construct from flags with default to asyncpg
    if args.sync:
        dsn = f"postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
        return dsn, False
    else:
        dsn = f"postgresql+asyncpg://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
        return dsn, True

def build_where(args: argparse.Namespace) -> Tuple[str, dict]:
    where = ""
    binds = {}
    if args.like:
        where = "WHERE filename ILIKE :like"
        binds["like"] = f"%{args.like}%"
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
    order_col = args.order_by if args.order_by in SAFE_ORDER_COLS else "created_at"
    order_dir = "ASC" if args.asc else "DESC"
    q = QUERY_PRIMARY.format(where=where, order_col=order_col, order_dir=order_dir)
    fb = QUERY_FALLBACK.format(where=where, order_col=order_col, order_dir=order_dir)
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
    order_col = args.order_by if args.order_by in SAFE_ORDER_COLS else "created_at"
    order_dir = "ASC" if args.asc else "DESC"
    q = QUERY_PRIMARY.format(where=where, order_col=order_col, order_dir=order_dir)
    fb = QUERY_FALLBACK.format(where=where, order_col=order_col, order_dir=order_dir)
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
