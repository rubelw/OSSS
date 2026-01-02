#!/usr/bin/env python3
"""
Generate/extend data/refiner_training_data.csv from a DBML schema,
using a local RAG/Ollama endpoint to synthesize raw_query/refined_query
examples for each table.

Directory layout (relative to this script in /data_model/refiner):

    - DBML schema: ../schema.dbml
    - Output CSV:  ./data/refiner_training_data.csv

- Reads table definitions from a DBML file (e.g. ../schema.dbml).
- For each table, sends its DBML block (schema + notes) to a local
  Ollama chat endpoint along with instructions.
- Expects the model to return JSON like:
    [
      {"raw_query": "...", "refined_query": "..."},
      ...
    ]
- Merges all generated rows into data/refiner_training_data.csv
  (or overwrites if --overwrite is passed).

Defaults assume a local Ollama server running on:
  http://localhost:11434/api/chat
with a model like "llama3.1" or "llama3".

Example usage (from /data_model/refiner):

    python populate_csv_data.py

    python populate_csv_data.py \\
        --dbml ../schema.dbml \\
        --csv data/refiner_training_data.csv

    python populate_csv_data.py \\
        --dbml ../schema.dbml \\
        --csv data/refiner_training_data.csv \\
        --district-short dcg \\
        --district-full "Dallas Center-Grimes School District" \\
        --ollama-endpoint http://localhost:11434/api/chat \\
        --ollama-model llama3.1 \\
        --examples-per-table 8
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict

import pandas as pd
import requests


# ---------------------------------------------------------------------------
# DBML parsing
# ---------------------------------------------------------------------------

TABLE_BLOCK_REGEX = re.compile(
    r"Table\s+([A-Za-z_][A-Za-z0-9_]*)\s*{(.*?)}",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class TableInfo:
    name: str
    block: str  # full DBML block for the table (columns, notes, etc.)

def append_rows_to_csv(
    csv_path: Path,
    rows: List[Dict[str, str]],
) -> None:
    """
    Append rows to CSV, creating it if needed and avoiding duplicate entries.
    """
    if not rows:
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(rows, columns=["raw_query", "refined_query"])

    if csv_path.exists():
        existing_df = pd.read_csv(csv_path)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["raw_query", "refined_query"])
        combined.to_csv(csv_path, index=False)
    else:
        new_df.to_csv(csv_path, index=False)


def extract_table_infos(dbml_text: str) -> List[TableInfo]:
    """
    Extracts table name + full DBML block for each table.

    Matches patterns like:

        Table student_school_enrollments {
            id uuid [pk]
            ...
            Note: 'Some description'
        }

    Returns a list[TableInfo].
    """
    infos: List[TableInfo] = []
    for match in TABLE_BLOCK_REGEX.finditer(dbml_text):
        name = match.group(1)
        block = match.group(2)
        infos.append(TableInfo(name=name, block=block))
    # Sort by name for reproducibility
    infos.sort(key=lambda t: t.name)
    return infos


# ---------------------------------------------------------------------------
# Simple fallback generator (used if Ollama/RAG fails)
# ---------------------------------------------------------------------------

def humanize_table_name(table_name: str) -> str:
    """
    Convert snake_case table name to a space-separated phrase.
    e.g. "student_school_enrollments" -> "student school enrollments"
    """
    return table_name.replace("_", " ")


def fallback_generate_examples_for_table(
    table_name: str,
    district_short: str,
    district_full: str,
    n_examples: int = 3,
) -> List[Dict[str, str]]:
    """
    Very simple backup: template-based examples in case the Ollama/RAG call fails.
    """
    label = humanize_table_name(table_name)
    ds = district_short.lower()
    refined = f"query {table_name} in {district_full}"

    base_patterns = [
        f"{ds} {label}",
        f"show me {ds} {label}",
        f"{ds} {label} list",
    ]

    rows: List[Dict[str, str]] = []
    for raw in base_patterns[:n_examples]:
        rows.append({"raw_query": raw, "refined_query": refined})
    return rows


# ---------------------------------------------------------------------------
# Ollama / local RAG integration
# ---------------------------------------------------------------------------

def call_ollama_for_table_examples(
    table: TableInfo,
    district_short: str,
    district_full: str,
    ollama_endpoint: str,
    ollama_model: str,
    examples_per_table: int,
    timeout: int = 90,
) -> List[Dict[str, str]]:
    """
    Call local Ollama chat endpoint to generate training examples.

    Assumes an Ollama-compatible API:

        POST {ollama_endpoint}
        JSON body:
        {
          "model": "<ollama_model>",
          "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."}
          ],
          "stream": false
        }

    And response like:
        {
          "model": "...",
          "created_at": "...",
          "message": {
            "role": "assistant",
            "content": "[{...}, {...}]"
          },
          "done": true,
          ...
        }

    Where `message.content` is EXACTLY valid JSON: a list of objects
    with 'raw_query' and 'refined_query' fields.
    """
    system_prompt = (
        "You generate supervised training data examples for a query refiner.\n"
        "The refiner maps free-form natural language queries into normalized "
        "action strings that the backend can route on.\n\n"
        "You MUST respond with ONLY valid JSON. Do not add any explanation, "
        "markdown, or text before or after the JSON. The JSON must be a list "
        "of objects, each with exactly two keys:\n"
        '  - \"raw_query\": a natural language query string\n'
        '  - \"refined_query\": a normalized query string\n\n'
        "The refined_query should:\n"
        "  - Start with an action verb like 'query', 'create', 'update', 'delete'\n"
        "  - Explicitly name the table (e.g. 'query student_school_enrollments')\n"
        "  - End with 'in <district_full>' when the query is scoped to a district.\n"
        "Do not return markdown code fences like ```json or ```dbml. "
        "Return only raw JSON.\n"
    )

    user_prompt = (
        f"You are generating training data for a query refiner in a school software system.\n\n"
        f"The school district short name is \"{district_short}\", and the full name is \"{district_full}\".\n"
        f"The user often uses the short name (e.g. \"{district_short}\") in their raw queries.\n\n"
        f"We are focusing on the table \"{table.name}\". Here is its DBML definition:\n\n"
        f"Table {table.name} {{\n"
        f"{table.block.strip()}\n"
        f"}}\n\n"
        f"Using that context, generate exactly {examples_per_table} realistic user queries "
        f"for this table. Mix up the phrasing and include different verbs that a user "
        f"might type when they want to interact with this data (e.g. 'show me', 'find', "
        f"'get', 'list', 'pull', 'look up', 'see', 'update', 'change', 'delete', etc.).\n\n"
        f"Guidelines:\n"
        f"- raw_query:\n"
        f"  * Natural language that a staff member in {district_full} might type.\n"
        f"  * Often mention the short code \"{district_short}\" when referring to the district.\n"
        f"  * Can optionally mention concepts implied by the columns/notes, but do not invent columns.\n"
        f"- refined_query:\n"
        f"  * A short, normalized command that your backend will route on.\n"
        f"  * Usually starts with \"query \" for read-type queries, or \"create \", \"update \", \"delete \" for write-type queries.\n"
        f"  * Must explicitly mention the table name {table.name}.\n"
        f"  * Should end with \"in {district_full}\" when the query is district-scoped.\n\n"
        f"Return ONLY a JSON list. DO NOT return markdown, backticks, or explanation.\n"
        f"Example format (illustrative only):\n\n"
        f"[\n"
        f"  {{\"raw_query\": \"{district_short} teachers\", \"refined_query\": \"query teacher_profiles in {district_full}\"}},\n"
        f"  {{\"raw_query\": \"show me {district_short} grades\", \"refined_query\": \"query student_grades in {district_full}\"}}\n"
        f"]\n"
    )

    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }

    resp = requests.post(ollama_endpoint, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # For Ollama /api/chat, the content lives under data["message"]["content"]
    content = data.get("message", {}).get("content", "").strip()
    if not content:
        raise ValueError("Empty content from Ollama response")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Ollama JSON content: {e}\nContent (truncated): {content[:500]}")

    if not isinstance(parsed, list):
        raise ValueError("Ollama JSON response is not a list")

    rows: List[Dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        raw = item.get("raw_query")
        ref = item.get("refined_query")
        if not raw or not ref:
            continue
        rows.append(
            {
                "raw_query": str(raw),
                "refined_query": str(ref),
            }
        )

    if not rows:
        raise ValueError("No valid (raw_query, refined_query) pairs produced by Ollama")

    return rows


def generate_and_append_rows_with_ollama(
    tables: Iterable[TableInfo],
    csv_path: Path,
    district_short: str,
    district_full: str,
    ollama_endpoint: str,
    ollama_model: str,
    examples_per_table: int,
) -> None:
    """
    For each table:
      - Call Ollama
      - Append results to CSV immediately
      - Fall back to templates if Ollama fails
    """

    for table in tables:
        print(f"\nGenerating examples for table: {table.name}")

        try:
            rows = call_ollama_for_table_examples(
                table=table,
                district_short=district_short,
                district_full=district_full,
                ollama_endpoint=ollama_endpoint,
                ollama_model=ollama_model,
                examples_per_table=examples_per_table,
            )
            print(f"  -> got {len(rows)} examples from Ollama")
        except Exception as e:
            print(f"  !! Ollama failed for {table.name}: {e}")
            print("  -> Using fallback examples")
            rows = fallback_generate_examples_for_table(
                table_name=table.name,
                district_short=district_short,
                district_full=district_full,
                n_examples=min(examples_per_table, 3),
            )

        append_rows_to_csv(csv_path, rows)
        print(f"  -> appended {len(rows)} rows to {csv_path}")


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate/extend refiner_training_data.csv from DBML tables using local Ollama/RAG."
    )
    parser.add_argument(
        "--dbml",
        type=str,
        default="../schema.dbml",
        help="Path to DBML schema file (default: ../schema.dbml)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="data/refiner_training_data.csv",
        help="Path to training CSV (default: data/refiner_training_data.csv)",
    )
    parser.add_argument(
        "--district-short",
        type=str,
        default="dcg",
        help='Short district label used in raw queries (default: "dcg")',
    )
    parser.add_argument(
        "--district-full",
        type=str,
        default="Dallas Center-Grimes School District",
        help=(
            "Full district name used in refined_query "
            '(default: "Dallas Center-Grimes School District")'
        ),
    )
    parser.add_argument(
        "--ollama-endpoint",
        type=str,
        default="http://localhost:11434/api/chat",
        help="URL of the local Ollama chat endpoint (default: http://localhost:11434/api/chat)",
    )
    parser.add_argument(
        "--ollama-model",
        type=str,
        default="llama3.1",
        help='Ollama model name (default: "llama3.1")',
    )
    parser.add_argument(
        "--examples-per-table",
        type=int,
        default=6,
        help="Number of examples to generate per table (default: 6)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="If set, overwrite CSV instead of merging with existing rows.",
    )

    args = parser.parse_args()

    dbml_path = Path(args.dbml)
    csv_path = Path(args.csv)

    if not dbml_path.exists():
        raise SystemExit(f"DBML file not found: {dbml_path}")

    dbml_text = dbml_path.read_text(encoding="utf-8")
    tables = extract_table_infos(dbml_text)

    if not tables:
        raise SystemExit(f"No tables found in DBML file: {dbml_path}")

    print(f"Found {len(tables)} tables in {dbml_path}")

    generate_and_append_rows_with_ollama(
        tables=tables,
        csv_path=csv_path,
        district_short=args.district_short,
        district_full=args.district_full,
        ollama_endpoint=args.ollama_endpoint,
        ollama_model=args.ollama_model,
        examples_per_table=args.examples_per_table,
    )

    print(f"\nDone. CSV updated incrementally at {csv_path}")


if __name__ == "__main__":
    main()
