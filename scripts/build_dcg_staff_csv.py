#!/usr/bin/env python3
import time
import csv
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://dcgschools.com/staff-directory/"
OUTPUT_CSV = "dcg_staff_and_employees.csv"

TOTAL_PAGES = 27  # directory currently has 27 pages


def fetch_page_html(page: int) -> str:
    """
    Page 1 uses the base URL directly.
    Pages 2-27 use /page/{page}/.
    """
    if page == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}page/{page}/"
    print(f"Fetching {url} ...")

    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_staff_from_page(html: str):
    """
    Extract Name, Title, Email using a robust pattern:

    We scan for lines with '@dcgschools.com', then walk backwards to find:

      - nearest previous non-empty, non-'Image:' line  -> title
      - previous non-empty, non-'Image:' line         -> name

    This avoids assuming fixed offsets like i-3 / i-2, which can break
    when the theme adds/removes blank lines.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    # Keep ALL lines, including blanks, so relative positions are preserved
    lines = [line.rstrip() for line in text.splitlines()]

    staff = []

    def is_junk(line: str) -> bool:
        # Lines we never want to treat as name/title
        if not line.strip():
            return True
        lowered = line.lower()
        if "image:" in lowered:
            return True
        if "staff directory" in lowered:
            return True
        if "all schools" in lowered:
            return True
        if "all departments" in lowered:
            return True
        if "search" == lowered:
            return True
        return False

    for i, line in enumerate(lines):
        if "@dcgschools.com" not in line:
            continue

        email = line.strip()
        if not email:
            continue

        # ---- walk backwards for title ----
        title = ""
        name = ""

        j = i - 1
        while j >= 0:
            candidate = lines[j].strip()
            if not candidate:
                j -= 1
                continue
            if "@" in candidate:
                j -= 1
                continue
            if "image:" in candidate.lower():
                j -= 1
                continue
            # first non-junk line above email -> title
            title = candidate
            j -= 1
            break

        # ---- walk further backwards for name ----
        while j >= 0:
            candidate = lines[j].strip()
            if not candidate:
                j -= 1
                continue
            if "@" in candidate:
                j -= 1
                continue
            if "image:" in candidate.lower():
                j -= 1
                continue
            if "staff directory" in candidate.lower():
                j -= 1
                continue
            if "all schools" in candidate.lower():
                j -= 1
                continue
            # first non-junk line above title -> name
            name = candidate
            break

        # Require at least a name + email
        if name and email:
            staff.append(
                {
                    "name": name,
                    "title": title,
                    "email": email,
                }
            )

    return staff


def scrape_all_staff():
    all_staff = []

    # Page 1
    html = fetch_page_html(1)
    staff = parse_staff_from_page(html)
    print(f"  Page 1: {len(staff)} staff entries")
    all_staff.extend(staff)

    # Pages 2 → TOTAL_PAGES
    for page in range(2, TOTAL_PAGES + 1):
        html = fetch_page_html(page)
        staff = parse_staff_from_page(html)
        print(f"  Page {page}: {len(staff)} staff entries")
        all_staff.extend(staff)
        time.sleep(0.4)  # be polite

    # Deduplicate by (name, email)
    unique = {}
    for s in all_staff:
        key = (s["name"], s["email"])
        if key not in unique:
            unique[key] = s

    staff_list = list(unique.values())

    # Sort alphabetically by last name
    def sort_key(s):
        parts = s["name"].split()
        return (parts[-1].lower(), s["name"].lower())

    staff_list.sort(key=sort_key)
    return staff_list


def write_csv(staff_list):
    print(f"Writing CSV to {OUTPUT_CSV} ...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "title", "email"])
        writer.writeheader()
        writer.writerows(staff_list)
    print(f"CSV completed: {OUTPUT_CSV}")


def main():
    staff = scrape_all_staff()
    print(f"Total unique staff entries: {len(staff)}")
    write_csv(staff)


if __name__ == "__main__":
    main()
