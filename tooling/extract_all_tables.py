#!/usr/bin/env python3

"""List ALL tables (not just non-empty) and save to CSV 'tables.csv'.

Connection values can be set via env vars:
  PGDATABASE, PGUSER, PGPASSWORD, PGHOST, PGPORT
Defaults are the OSSS dev values used previously.
"""
import os
import csv
import psycopg2

DB_NAME = os.getenv("PGDATABASE", "osss")
DB_USER = os.getenv("PGUSER", "osss")
DB_PASS = os.getenv("PGPASSWORD", "password")
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5433")

OUTPUT_CSV = "tables.csv"

def list_all_tables(include_system=False):
    """Return [(schema, table)] for all base tables.
    If include_system=False, skip pg_catalog/information_schema.
    """
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
    )
    try:
        with conn, conn.cursor() as cur:
            if include_system:
                cur.execute(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_type='BASE TABLE'
                    ORDER BY table_schema, table_name
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_type='BASE TABLE'
                      AND table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name
                    """
                )
            return cur.fetchall()
    finally:
        conn.close()

def write_csv(rows, path=OUTPUT_CSV):
    """Write rows [(schema, table)] to CSV with headers."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table_schema", "table_name"])
        for schema, table in rows:
            w.writerow([schema, table])

if __name__ == "__main__":
    tables = list_all_tables(include_system=False)
    write_csv(tables, OUTPUT_CSV)
    # Also echo a friendly summary to stdout
    count = len(tables)
    unique_schemas = sorted(set(s for s, _ in tables))
    print(f"Wrote {count} table(s) across {len(unique_schemas)} schema(s) to {OUTPUT_CSV}.")
    if unique_schemas:
        print("Schemas:", ", ".join(unique_schemas))
