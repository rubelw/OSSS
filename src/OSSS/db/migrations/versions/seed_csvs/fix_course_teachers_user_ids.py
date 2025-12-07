#!/usr/bin/env python3
"""
Fix course_teachers.csv so user_id always points at an existing users.id.

Usage (from seed_csvs/):
  python fix_course_teachers_user_ids.py \
      --csv-dir ../csv \
      --users users.csv \
      --course-teachers course_teachers.csv
"""

from __future__ import annotations
import argparse
import csv
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", default="../csv")
    parser.add_argument("--users", default="users.csv")
    parser.add_argument("--course-teachers", default="course_teachers.csv")
    args = parser.parse_args()

    csv_dir = Path(__file__).resolve().parent / args.csv_dir
    users_path = csv_dir / args.users
    ct_path = csv_dir / args.course_teachers

    # 1) Load valid user IDs
    with users_path.open(newline="", encoding="utf8") as f:
        reader = csv.DictReader(f)
        user_ids = [row["id"].strip() for row in reader if row.get("id")]

    if not user_ids:
        raise SystemExit(f"No user IDs found in {users_path}")

    print(f"Loaded {len(user_ids)} users from {users_path}")

    # 2) Rewrite course_teachers.user_id to round-robin valid users
    with ct_path.open(newline="", encoding="utf8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if "user_id" not in fieldnames:
        raise SystemExit(f"'user_id' column not found in {ct_path}")

    for idx, row in enumerate(rows):
        row["user_id"] = user_ids[idx % len(user_ids)]

    backup = ct_path.with_suffix(".csv.bak")
    ct_path.rename(backup)
    print(f"Backed up original to {backup}")

    with ct_path.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Rewrote {len(rows)} rows in {ct_path}")

if __name__ == "__main__":
    main()
