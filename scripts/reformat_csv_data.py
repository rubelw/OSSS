#!/usr/bin/env python3

#!/usr/bin/env python3
import csv
import re
import sys

def normalize_name(name: str) -> str:
    # Turn " -XYZ" suffixes into " XYZ" (e.g., " -DSM" -> " DSM")
    name = re.sub(r"\s*-\s*([A-Za-z0-9]+)$", r" \1", name.strip())
    return name.replace('"', r'\"')

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    fh = sys.stdin if src == "-" else open(src, newline="", encoding="utf-8")
    with fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            code = row[0].strip()
            # Join in case the name field itself contains commas
            name = ",".join(row[1:]).strip()
            name = normalize_name(name)
            print(f'("{code}", "{name}"),')

if __name__ == "__main__":
    main()
