#!/usr/bin/env python3
"""
Train a simple intent classifier and save it to models/intent_classifier.joblib.

Changes vs. original:
- Training data is stored in a JSON file (default: data/intent_training_data.json)
- Script will create the JSON file with starter examples if it doesn't exist
- You can dynamically update the dataset via CLI flags (add examples) and retrain
- Optionally bootstrap/generate synthetic labeled examples via a local OpenAI-compatible
  /v1/chat/completions endpoint and append them to the JSON.
- NEW: debug/trace output:
  - show the exact request JSON sent to the LLM
  - show raw response JSON from the LLM (or a truncated version)
  - show what is written to the training JSON file (either full file or delta)
- NEW: robust JSON extraction from LLM content:
  - supports the model returning multiple JSON objects back-to-back
  - merges all "examples" lists found
- NEW: de-dupe safety:
  - checks existing JSON file contents + current run additions to avoid duplicates
- NEW: continuous learning mode:
  - keep generating in batches until stopped (Ctrl+C), or optional stop conditions

Examples:
  ./train_intent_classifier.py
  ./train_intent_classifier.py --add "How do I reset a password?" --label informational
  ./train_intent_classifier.py --bootstrap-from-llm --n-per-label 30 --trace-llm --trace-json

  # Continuous learning (Ctrl+C to stop)
  ./train_intent_classifier.py --bootstrap-from-llm --continuous --batch-size 20 --trace-llm --trace-json
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys
from typing import Any, Dict, List, Tuple, Optional

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


DEFAULT_DATA_PATH = Path("data") / "intent_training_data.json"
DEFAULT_MODEL_PATH = Path("models") / "intent_classifier.joblib"


# Starter examples (only used to bootstrap the JSON file if missing)
DEFAULT_TRAINING_DATA: List[Tuple[str, str]] = [
    # informational
    ("List the DCG School Board Members", "informational"),
    ("What is OSSS?", "informational"),
    ("Explain pgvector", "informational"),
    ("How do I configure Terraform for S3?", "informational"),
    ("What is the capital of France?", "informational"),
    ("Show me my schedule for tomorrow", "informational"),
    # action / task
    ("Create a new student record", "action"),
    ("Update the teacher email for John Smith", "action"),
    ("Delete the test administration for grade 5", "action"),
    ("Generate a report card PDF for student 123", "action"),
    ("Add a new course called Algebra II", "action"),
    ("Import this CSV into the database", "action"),
    # troubleshooting / debugging
    ("Why is my FastAPI app crashing on startup?", "troubleshooting"),
    ("SQLAlchemy NoForeignKeysError on Topic.parent", "troubleshooting"),
    ("Kubernetes deployment stuck in CrashLoopBackOff", "troubleshooting"),
    ("Terraform plan fails with missing provider", "troubleshooting"),
    ("OpenAI request_id is None and logging fails JSON serialization", "troubleshooting"),
    ("Starburst query spillable not set yet", "troubleshooting"),
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(s: str) -> str:
    # Light normalization to reduce duplicate noise
    return " ".join((s or "").strip().split())


def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)


def _print_block(title: str, body: str) -> None:
    print(f"\n{'=' * 10} {title} {'=' * 10}")
    print(body)
    print(f"{'=' * (22 + len(title))}\n")


def ensure_training_json(path: Path) -> None:
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": utc_now_iso(),
        "examples": [{"text": t, "label": y} for t, y in DEFAULT_TRAINING_DATA],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[init] Created starter training data JSON at: {path.resolve()}")


def load_training_json(path: Path) -> Dict[str, Any]:
    ensure_training_json(path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as e:
        raise SystemExit(f"Failed to read/parse training JSON at {path}: {e}") from e

    if not isinstance(data, dict):
        raise SystemExit(f"Training JSON must be an object at top-level: {path}")

    examples = data.get("examples")
    if not isinstance(examples, list):
        raise SystemExit(f"Training JSON must contain 'examples' as a list: {path}")

    return data


def save_training_json(path: Path, data: Dict[str, Any]) -> None:
    data["updated_at"] = utc_now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_examples(
    data: Dict[str, Any],
    additions: List[Tuple[str, str]],
    *,
    allow_duplicates: bool,
) -> int:
    """
    Adds (text,label) pairs into data["examples"] with de-dupe against:
      - what is already in the JSON file
      - what has already been added this run
    """
    examples = data.setdefault("examples", [])
    if not isinstance(examples, list):
        raise SystemExit("Invalid training JSON: 'examples' must be a list")

    existing: set[tuple[str, str]] = set()
    for ex in examples:
        if not isinstance(ex, dict):
            continue
        t = normalize_text(str(ex.get("text", ""))).lower()
        y = normalize_text(str(ex.get("label", ""))).lower()
        if t and y:
            existing.add((t, y))

    added = 0
    for text, label in additions:
        t_norm = normalize_text(text)
        y_norm = normalize_text(label).lower()
        if not t_norm or not y_norm:
            continue

        key = (t_norm.lower(), y_norm)

        if (not allow_duplicates) and (key in existing):
            continue

        examples.append({"text": t_norm, "label": y_norm})
        existing.add(key)
        added += 1

    return added


def to_training_pairs(data: Dict[str, Any]) -> List[Tuple[str, str]]:
    examples = data.get("examples", [])
    pairs: List[Tuple[str, str]] = []

    for ex in examples:
        if not isinstance(ex, dict):
            continue
        text = normalize_text(str(ex.get("text", "")))
        label = normalize_text(str(ex.get("label", ""))).lower()
        if not text or not label:
            continue
        pairs.append((text, label))

    # Deduplicate while preserving order
    seen: set[tuple[str, str]] = set()
    deduped: List[Tuple[str, str]] = []
    for t, y in pairs:
        key = (t.lower(), y)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((t, y))

    return deduped


def print_label_stats(pairs: List[Tuple[str, str]]) -> None:
    counts: Dict[str, int] = {}
    for _, y in pairs:
        counts[y] = counts.get(y, 0) + 1
    total = sum(counts.values())
    stats = ", ".join([f"{k}={v}" for k, v in sorted(counts.items())])
    print(f"[data] examples={total} ({stats})")


def train_and_save(pairs: List[Tuple[str, str]], model_path: Path) -> None:
    if not pairs:
        raise SystemExit("No valid training examples found; cannot train model.")

    texts = [t for t, _ in pairs]
    labels = [y for _, y in pairs]

    pipeline = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=2000)),
        ]
    )

    pipeline.fit(texts, labels)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    print(f"[model] Saved model to: {model_path.resolve()}")


def _summarize_write_delta(
    before: Dict[str, Any],
    after: Dict[str, Any],
    *,
    max_items: int,
) -> str:
    """
    Show what changed in a concise way (by default): how many examples added
    and a preview of the last N examples after the update.
    """
    before_ex = before.get("examples", [])
    after_ex = after.get("examples", [])
    if not isinstance(before_ex, list) or not isinstance(after_ex, list):
        return "<unable to summarize delta: examples is not a list>"

    added_count = max(0, len(after_ex) - len(before_ex))
    tail = after_ex[-min(max_items, len(after_ex)):] if after_ex else []
    return _pretty_json(
        {
            "added_count": added_count,
            "before_examples_count": len(before_ex),
            "after_examples_count": len(after_ex),
            "preview_last_examples": tail,
        }
    )


# ---------------------------------------------------------------------------
# LLM bootstrap helpers
# ---------------------------------------------------------------------------

def _call_local_chat_completions(
    prompt: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
    temperature: float,
    use_rag: bool,
    top_k: int,
    max_tokens: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> Tuple[str, Dict[str, Any], str, Dict[str, Any]]:
    """
    Calls an OpenAI-compatible /v1/chat/completions endpoint and returns:
      - assistant content string (choices[0].message.content)
      - parsed response JSON envelope (full)
      - raw response text (string)
      - request JSON payload (dict)
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate training examples for an intent classifier.\n\n"

                    "CRITICAL LABELING RULES:\n"
                    "1. If a user query asks to list, show, search, filter, count, query, "
                    "create, update, or delete records from ANY OSSS database table, "
                    "the label MUST be 'action'.\n"
                    "2. This applies EVEN IF the query is phrased like a question.\n"
                    "3. Only use the labels: informational, action, troubleshooting.\n\n"

                    "DATABASE TABLE TRIGGER:\n"
                    "If the query mentions ANY of the following table names (case-insensitive), "
                    "you MUST label it as 'action' because it requires querying the backend database:\n\n"

                    "academic_terms, accommodations, activities, addresses, agenda_item_approvals, "
                    "agenda_item_files, agenda_items, agenda_workflow_steps, agenda_workflows, "
                    "alembic_version, alignments, ap_vendors, approvals, asset_parts, assets, "
                    "assignment_categories, assignments, attendance, attendance_codes, "
                    "attendance_daily_summary, attendance_events, audit_logs, behavior_codes, "
                    "behavior_interventions, bell_schedules, buildings, bus_routes, bus_stop_times, "
                    "bus_stops, calendar_days, calendars, channels, class_ranks, comm_search_index, "
                    "committees, compliance_records, consents, consequence_types, consequences, "
                    "contacts, course_prerequisites, course_sections, courses, curricula, "
                    "curriculum_units, curriculum_versions, data_quality_issues, "
                    "data_sharing_agreements, deduction_codes, deliveries, "
                    "department_position_index, departments, document_activity, document_links, "
                    "document_notifications, document_permissions, document_search_index, "
                    "document_versions, documents, earning_codes, education_associations, ell_plans, "
                    "embeds, emergency_contacts, employee_deductions, employee_earnings, entity_tags, "
                    "evaluation_assignments, evaluation_cycles, evaluation_files, "
                    "evaluation_questions, evaluation_reports, evaluation_responses, "
                    "evaluation_sections, evaluation_signoffs, evaluation_templates, events, "
                    "export_runs, external_ids, facilities, family_portal_access, feature_flags, "
                    "fees, files, final_grades, fiscal_periods, fiscal_years, floors, folders, "
                    "frameworks, gl_account_balances, gl_account_segments, gl_accounts, "
                    "gl_segment_values, gl_segments, goals, google_accounts, governing_bodies, "
                    "gpa_calculations, grade_levels, grade_scale_bands, grade_scales, "
                    "gradebook_entries, grading_periods, guardians, health_profiles, hr_employees, "
                    "hr_position_assignments, hr_positions, iep_plans, immunization_records, "
                    "immunizations, incident_participants, incidents, initiatives, invoices, "
                    "journal_batches, journal_entries, journal_entry_lines, kpi_datapoints, kpis, "
                    "leases, library_checkouts, library_fines, library_holds, library_items, "
                    "maintenance_requests, meal_accounts, meal_eligibility_statuses, "
                    "meal_transactions, medication_administrations, medications, meeting_documents, "
                    "meeting_files, meeting_permissions, meeting_publications, "
                    "meeting_search_index, meetings, memberships, message_recipients, messages, "
                    "meters, minutes, motions, move_orders, notifications, nurse_visits, objectives, "
                    "order_line_items, orders, organizations, pages, part_locations, parts, "
                    "pay_periods, paychecks, payments, payroll_runs, periods, permissions, "
                    "person_addresses, person_contacts, personal_notes, persons, plan_alignments, "
                    "plan_assignments, plan_filters, plan_search_index, plans, pm_plans, "
                    "pm_work_generators, policies, policy_approvals, policy_comments, policy_files, "
                    "policy_legal_refs, policy_publications, policy_search_index, policy_versions, "
                    "policy_workflow_steps, policy_workflows, post_attachments, posts, project_tasks, "
                    "projects, proposal_documents, proposal_reviews, proposal_standard_map, "
                    "proposals, publications, report_cards, requirements, resolutions, "
                    "retention_rules, review_requests, review_rounds, reviewers, reviews, "
                    "role_permissions, roles, rooms, round_decisions, scan_requests, scan_results, "
                    "schools, scorecard_kpis, scorecards, section504_plans, section_meetings, "
                    "section_room_assignments, sis_import_jobs, space_reservations, spaces, "
                    "special_education_cases, staff, standardized_tests, standards, "
                    "state_reporting_snapshots, states, student_guardians, "
                    "student_program_enrollments, student_school_enrollments, "
                    "student_section_enrollments, student_transportation_assignments, students, "
                    "subjects, subscriptions, tags, teacher_section_assignments, "
                    "test_administrations, test_results, ticket_scans, ticket_types, tickets, "
                    "transcript_lines, unit_standard_map, user_accounts, users, vendors, votes, "
                    "waivers, warranties, webhooks, work_order_parts, work_order_tasks, "
                    "work_order_time_logs, work_orders.\n\n"

                    "OUTPUT CONSTRAINTS:\n"
                    "- Return EXACTLY ONE JSON object and NOTHING ELSE.\n"
                    "- Top-level MUST be an object with key 'examples' (a list).\n"
                    "- Each item MUST be: {\"text\": \"...\", \"label\": \"...\"}\n"
                    "- Do NOT include markdown, comments, or extra text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
        "use_rag": bool(use_rag),
        "top_k": int(top_k),
    }

    if trace_llm:
        _print_block("LLM REQUEST (json)", _pretty_json(payload))

    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = "<failed to read error body>"
        raise SystemExit(f"LLM endpoint HTTPError {e.code}: {body}")
    except URLError as e:
        raise SystemExit(f"LLM endpoint connection failed: {e}")
    except Exception as e:
        raise SystemExit(f"LLM endpoint error: {e}")

    try:
        obj = json.loads(raw)
    except Exception as e:
        raise SystemExit(f"Failed to parse LLM response envelope as JSON: {e}\nRaw:\n{raw}")

    if trace_llm:
        shown = raw
        if trace_llm_max_chars > 0 and len(shown) > trace_llm_max_chars:
            shown = shown[:trace_llm_max_chars] + "\n...<truncated>..."
        _print_block("LLM RESPONSE (raw json)", shown)

    try:
        content = obj["choices"][0]["message"]["content"]
    except Exception as e:
        raise SystemExit(f"LLM response missing choices[0].message.content: {e}\nRaw:\n{raw}")

    return str(content), obj, raw, payload


def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """
    Extract one or more top-level JSON objects from a string.
    Handles cases where the model returns multiple JSON objects back-to-back
    (or with whitespace between them).

    Returns a list of dicts (top-level objects only).
    """
    s = text.strip()
    objs: List[Dict[str, Any]] = []

    # Fast path: single JSON document
    try:
        one = json.loads(s)
        if isinstance(one, dict):
            return [one]
        return []
    except json.JSONDecodeError:
        pass

    # Slow path: scan for balanced {...} objects and try json.loads on each slice
    start: Optional[int] = None
    depth = 0
    in_str = False
    escape = False

    for i, ch in enumerate(s):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    chunk = s[start : i + 1]
                    start = None
                    try:
                        obj = json.loads(chunk)
                        if isinstance(obj, dict):
                            objs.append(obj)
                    except json.JSONDecodeError:
                        pass

    return objs


def _generate_intent_examples_via_llm(
    *,
    endpoint: str,
    model: str,
    labels: List[str],
    n_per_label: int,
    timeout_seconds: float,
    temperature: float,
    use_rag: bool,
    top_k: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> List[Tuple[str, str]]:
    """
    Asks the LLM to generate labeled training examples in strict JSON format.

    Expected content schema:
      { "examples": [ { "text": "...", "label": "informational" }, ... ] }

    Robustness:
      - If the model returns multiple JSON objects, we extract them all and merge
        all "examples" lists found.
    """
    labels_norm = [normalize_text(x).lower() for x in labels if normalize_text(x)]
    labels_norm = [x for i, x in enumerate(labels_norm) if x and x not in labels_norm[:i]]
    if not labels_norm:
        raise SystemExit("No valid --labels provided for LLM bootstrap.")

    prompt = f"""
Generate {int(n_per_label)} SHORT, realistic user queries for EACH label in: {labels_norm}.

Rules:
- Output MUST be valid JSON (no markdown fences).
- Return ONE object: {{ "examples": [ ... ] }}
- Each list item MUST be: {{ "text": "...", "label": "..." }}
- Labels MUST be exactly one of: {labels_norm}
- "text" must be a single user query (not an answer), typically 5-14 words.
- Include a mix: DCG/district questions, OSSS/admin app questions, and devops/debugging questions.
- Avoid personal emails/phone numbers/URLs.

Return ONLY the JSON object.
""".strip()

    content, envelope, _raw, _payload = _call_local_chat_completions(
        prompt,
        endpoint=endpoint,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        use_rag=use_rag,
        top_k=top_k,
        max_tokens=1200,
        trace_llm=trace_llm,
        trace_llm_max_chars=trace_llm_max_chars,
    )

    if trace_llm:
        shown = content
        if trace_llm_max_chars > 0 and len(shown) > trace_llm_max_chars:
            shown = shown[:trace_llm_max_chars] + "\n...<truncated>..."
        _print_block("LLM CONTENT (choices[0].message.content)", shown)

        if isinstance(envelope, dict) and "rag" in envelope:
            _print_block("LLM RAG METADATA (from response)", _pretty_json(envelope.get("rag")))

    objs = _extract_json_objects(content)
    if not objs:
        raise SystemExit(f"LLM did not return parseable JSON object(s).\nContent:\n{content}")

    merged_examples: List[Any] = []
    for obj in objs:
        ex = obj.get("examples")
        if isinstance(ex, list):
            merged_examples.extend(ex)

    if not merged_examples:
        keys = [list(o.keys()) for o in objs]
        raise SystemExit(f"LLM JSON missing 'examples' list in all objects. Keys={keys}\nContent:\n{content}")

    allowed = set(labels_norm)
    out: List[Tuple[str, str]] = []
    for item in merged_examples:
        if not isinstance(item, dict):
            continue
        t = normalize_text(str(item.get("text", "")))
        y = normalize_text(str(item.get("label", ""))).lower()
        if not t or not y:
            continue
        if y not in allowed:
            continue
        out.append((t, y))

    return out


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train intent classifier from JSON training data.")
    p.add_argument(
        "--data",
        default=str(DEFAULT_DATA_PATH),
        help=f"Path to training data JSON (default: {DEFAULT_DATA_PATH})",
    )
    p.add_argument(
        "--out",
        default=str(DEFAULT_MODEL_PATH),
        help=f"Path to output model joblib (default: {DEFAULT_MODEL_PATH})",
    )
    p.add_argument(
        "--add",
        action="append",
        default=[],
        help="Add a training example text (pair with --label). Can be used multiple times.",
    )
    p.add_argument(
        "--label",
        action="append",
        default=[],
        help="Label for the corresponding --add. Can be used multiple times.",
    )
    p.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="If set, do not dedupe when adding examples.",
    )

    # Bootstrap examples using local /v1/chat/completions
    p.add_argument(
        "--bootstrap-from-llm",
        action="store_true",
        help="Generate synthetic labeled examples from a local OpenAI-compatible /v1/chat/completions endpoint and append to JSON before training.",
    )
    p.add_argument(
        "--llm-endpoint",
        default="http://localhost:8081/v1/chat/completions",
        help="Chat completions endpoint (default: http://localhost:8081/v1/chat/completions)",
    )
    p.add_argument(
        "--llm-model",
        default="llama3.1",
        help="Model name to use at the endpoint (default: llama3.1)",
    )
    p.add_argument(
        "--labels",
        default="informational,action,troubleshooting",
        help="Comma-separated labels to generate (default: informational,action,troubleshooting)",
    )
    p.add_argument(
        "--n-per-label",
        type=int,
        default=20,
        help="How many examples per label to generate (default: 20). Also used as default batch size unless --batch-size is set.",
    )
    p.add_argument(
        "--llm-timeout",
        type=float,
        default=60.0,
        help="Timeout (seconds) for the LLM endpoint request (default: 60)",
    )
    p.add_argument(
        "--llm-temperature",
        type=float,
        default=0.7,
        help="Temperature for generation (default: 0.7)",
    )
    p.add_argument(
        "--llm-use-rag",
        action="store_true",
        default=True,
        help="Include use_rag=true in the request body (default: true).",
    )
    p.add_argument(
        "--llm-no-rag",
        action="store_true",
        help="Disable use_rag for bootstrap (overrides --llm-use-rag).",
    )
    p.add_argument(
        "--llm-top-k",
        type=int,
        default=6,
        help="top_k for RAG retrieval (default: 6)",
    )

    # NEW: continuous learning controls
    p.add_argument(
        "--continuous",
        action="store_true",
        help="Keep generating batches from LLM until stopped (Ctrl+C).",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="How many examples per label to request per batch (default: uses --n-per-label).",
    )
    p.add_argument(
        "--max-new",
        type=int,
        default=0,
        help="Stop after adding this many NEW examples total (0 = no limit).",
    )
    p.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Sleep between batches (default: 0). Useful to avoid hammering the endpoint.",
    )
    p.add_argument(
        "--stop-after-stale-batches",
        type=int,
        default=0,
        help="Stop after N consecutive batches add 0 new examples (0 = never stop for staleness).",
    )
    p.add_argument(
        "--save-every-batch",
        action="store_true",
        default=True,
        help="Persist JSON after every batch (default: true).",
    )

    # NEW: tracing controls
    p.add_argument(
        "--trace-llm",
        action="store_true",
        help="Print the exact LLM request JSON and raw response JSON to stdout.",
    )
    p.add_argument(
        "--trace-llm-max-chars",
        type=int,
        default=8000,
        help="Max chars to print for LLM raw response/content blocks (default: 8000). Use 0 for no truncation.",
    )
    p.add_argument(
        "--trace-json",
        action="store_true",
        help="Print what will be written to the training JSON file (delta summary by default).",
    )
    p.add_argument(
        "--trace-json-full",
        action="store_true",
        help="If set with --trace-json, print the full JSON file content that will be written (can be very large).",
    )
    p.add_argument(
        "--trace-json-max-items",
        type=int,
        default=25,
        help="When showing JSON delta, show at most this many examples in the preview (default: 25).",
    )

    return p.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    data_path = Path(args.data)
    out_path = Path(args.out)

    # Keep a 'before' snapshot for delta reporting
    data_before = load_training_json(data_path)

    # IMPORTANT: deep copy so we can safely compute deltas
    data = json.loads(json.dumps(data_before))

    def _maybe_trace_json_write(before_obj: Dict[str, Any], after_obj: Dict[str, Any], *, reason: str) -> None:
        if not bool(getattr(args, "trace_json", False)):
            return
        if bool(getattr(args, "trace_json_full", False)):
            _print_block(f"JSON WRITE ({reason}) - FULL FILE", _pretty_json(after_obj))
        else:
            delta = _summarize_write_delta(
                before_obj,
                after_obj,
                max_items=int(getattr(args, "trace_json_max_items", 25)),
            )
            _print_block(f"JSON WRITE ({reason}) - DELTA SUMMARY", delta)

    # LLM bootstrap (runs before manual --add so you can override/fix after)
    if bool(getattr(args, "bootstrap_from_llm", False)):
        labels = [x.strip() for x in str(args.labels).split(",") if x.strip()]
        use_rag = bool(args.llm_use_rag) and (not bool(args.llm_no_rag))

        continuous = bool(getattr(args, "continuous", False))
        batch_size = int(getattr(args, "batch_size", 0)) or int(args.n_per_label)
        max_new = int(getattr(args, "max_new", 0))
        sleep_seconds = float(getattr(args, "sleep_seconds", 0.0))
        stop_after_stale = int(getattr(args, "stop_after_stale_batches", 0))
        save_every_batch = bool(getattr(args, "save_every_batch", True))

        total_added = 0
        stale_batches = 0
        batch_idx = 0

        print(
            f"[llm] bootstrap starting | continuous={continuous} batch_size={batch_size} "
            f"max_new={max_new or '∞'} use_rag={use_rag} top_k={int(args.llm_top_k)}"
        )

        try:
            while True:
                batch_idx += 1

                additions = _generate_intent_examples_via_llm(
                    endpoint=str(args.llm_endpoint),
                    model=str(args.llm_model),
                    labels=labels,
                    n_per_label=int(batch_size),
                    timeout_seconds=float(args.llm_timeout),
                    temperature=float(args.llm_temperature),
                    use_rag=use_rag,
                    top_k=int(args.llm_top_k),
                    trace_llm=bool(args.trace_llm),
                    trace_llm_max_chars=int(args.trace_llm_max_chars),
                )

                before_batch = json.loads(json.dumps(data))
                added_now = add_examples(data, additions, allow_duplicates=bool(args.allow_duplicates))
                total_added += added_now

                if added_now == 0:
                    stale_batches += 1
                else:
                    stale_batches = 0

                # Trace what we're about to write
                _maybe_trace_json_write(before_batch, data, reason=f"after LLM batch {batch_idx}")

                if save_every_batch:
                    save_training_json(data_path, data)

                print(
                    f"[llm] batch={batch_idx} generated={len(additions)} added={added_now} "
                    f"total_added={total_added} stale_batches={stale_batches}"
                )

                # Stop conditions
                if max_new > 0 and total_added >= max_new:
                    print(f"[llm] reached --max-new={max_new}; stopping bootstrap")
                    break

                if stop_after_stale > 0 and stale_batches >= stop_after_stale:
                    print(f"[llm] no new examples for {stale_batches} batches; stopping bootstrap")
                    break

                if not continuous:
                    break

                if sleep_seconds > 0:
                    import time as _time
                    _time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\n[llm] stopped by user (Ctrl+C)")

        # Ensure saved at end even if not saving every batch
        if not save_every_batch:
            _maybe_trace_json_write(data_before, data, reason="final save after bootstrap")
            save_training_json(data_path, data)
            print(f"[llm] saved updated training data to: {data_path.resolve()}")

        # update baseline "before" for subsequent deltas (CLI additions)
        data_before = json.loads(json.dumps(data))

    # Dynamic updates: add examples from CLI
    additions_raw: List[str] = args.add or []
    labels_raw: List[str] = args.label or []

    if additions_raw or labels_raw:
        if len(additions_raw) != len(labels_raw):
            raise SystemExit(
                f"--add and --label must have the same count. Got add={len(additions_raw)} label={len(labels_raw)}"
            )
        additions_cli: List[Tuple[str, str]] = list(zip(additions_raw, labels_raw))

        before_cli = json.loads(json.dumps(data))
        added_cli = add_examples(data, additions_cli, allow_duplicates=bool(args.allow_duplicates))

        _maybe_trace_json_write(before_cli, data, reason="after CLI additions")

        save_training_json(data_path, data)
        print(f"[update] Added {added_cli} example(s) to: {data_path.resolve()}")

    pairs = to_training_pairs(data)
    print_label_stats(pairs)

    train_and_save(pairs, out_path)


if __name__ == "__main__":
    main(sys.argv[1:])
