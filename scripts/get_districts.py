#!/usr/bin/env python3

import csv
import re

# Input text file with copied PDF content
input_file = "iowa_district_codes.txt"
# Output CSV file
output_file = "iowa_district_codes.csv"

# Regex to match code and district name
pattern = re.compile(r"^(\d{8})\s+([A-Za-z0-9 .'\-&()]+)", re.MULTILINE)

rows = []

with open(input_file, "r", encoding="utf-8") as f:
    text = f.read()

    # Find matches
    matches = pattern.findall(text)
    for code, name in matches:
        # Remove trailing spaces and parentheses content if desired
        clean_name = re.sub(r"\s*\([^)]*\)", "", name).strip()
        rows.append({"code": code, "district_name": clean_name})

# Write to CSV
with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=["code", "district_name"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Saved {len(rows)} districts to {output_file}")
