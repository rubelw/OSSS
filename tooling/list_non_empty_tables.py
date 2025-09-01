#!/usr/bin/env python3

import psycopg2
from psycopg2 import sql

def list_empty_tables():
    conn = psycopg2.connect(
        dbname="osss",        # change if your db name is different
        user="osss",          # change if your user is different
        password="password",  # set your password
        host="localhost",
        port="5433",
    )
    try:
        with conn, conn.cursor() as cur:
            # get all tables in the public schema
            cur.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public';
            """)
            tables = [row[0] for row in cur.fetchall()]

            empty_tables = []
            for table in tables:
                # SELECT COUNT(*) FROM public."table"
                cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}.{};")
                       .format(sql.Identifier('public'), sql.Identifier(table))
                )
                count = cur.fetchone()[0]
                if count != 0:
                    empty_tables.append(table)

            return empty_tables
    finally:
        conn.close()

if __name__ == "__main__":
    empties = list_empty_tables()
    if empties:
        # sort alphabetically (case-insensitive)
        empties = sorted(empties, key=str.lower)

        print("Empty tables:")
        for counter, t in enumerate(empties, start=1):
            print(f"- {t} - {counter}")
    else:
        print("No empty tables found.")
