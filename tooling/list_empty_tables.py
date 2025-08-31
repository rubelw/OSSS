#!/usr/bin/env python3

import psycopg2

def list_empty_tables():
    conn = psycopg2.connect(
        dbname="osss",     # change if your db name is different
        user="osss",       # change if your user is different
        password="password",  # set your password
        host="localhost",
        port="5433"
    )
    conn.autocommit = True
    cur = conn.cursor()

    # get all tables in the public schema
    cur.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public';
    """)
    tables = cur.fetchall()

    empty_tables = []
    for (table,) in tables:
        cur.execute(f"SELECT COUNT(*) FROM public.{table};")
        count = cur.fetchone()[0]
        if count == 0:
            empty_tables.append(table)

    cur.close()
    conn.close()

    return empty_tables

if __name__ == "__main__":
    empties = list_empty_tables()
    if empties:
        print("Empty tables:")
        for t in empties:
            print(f"- {t}")
    else:
        print("No empty tables found.")
