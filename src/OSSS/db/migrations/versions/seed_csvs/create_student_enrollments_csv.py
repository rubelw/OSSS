#!/usr/bin/env python3
import csv
import uuid
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent

students_csv = ROOT / "../raw_data/students.csv"
schools_csv = ROOT / "../raw_data/schools.csv"
grade_levels_csv = ROOT / "../csv/grade_levels.csv"
enrollments_csv = ROOT / "../raw_data/student_school_enrollments.csv"

# Load students
students = []
with students_csv.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        students.append(row)

# Load schools (we’ll cycle through them)
schools = []
with schools_csv.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        schools.append(row["id"])

if not schools:
    raise RuntimeError("No schools found in schools.csv")

# Load grade levels (we’ll also cycle through them)
grade_levels = []
with grade_levels_csv.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        grade_levels.append(row["id"])

if not grade_levels:
    raise RuntimeError("No grade levels found in grade_levels.csv")

print(f"Loaded {len(students)} students, {len(schools)} schools, {len(grade_levels)} grade levels")

# Write new student_school_enrollments.csv
fieldnames = [
    "student_id",
    "school_id",
    "entry_date",
    "exit_date",
    "status",
    "exit_reason",
    "grade_level_id",
    "created_at",
    "updated_at",
    "id",
]

with enrollments_csv.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

    for idx, student in enumerate(students, start=1):
        student_id = student["id"]

        # Cycle schools and grade levels to distribute
        school_id = schools[(idx - 1) % len(schools)]
        grade_level_id = grade_levels[(idx - 1) % len(grade_levels)]

        entry_date = "2024-08-23"
        exit_date = ""  # still enrolled

        row = {
            "student_id": student_id,
            "school_id": school_id,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "status": "ENROLLED",
            "exit_reason": "",
            "grade_level_id": grade_level_id,
            "created_at": "2024-08-23T08:00:00Z",
            "updated_at": "2024-08-23T08:00:00Z",
            "id": str(uuid.uuid5(uuid.UUID("00000000-0000-0000-0000-000000000001"),
                                 f"student_school_enrollment:{student_id}")),
        }

        writer.writerow(row)

print(f"Wrote {enrollments_csv}")
