#!/usr/bin/env python3
"""
Build a training_data-style JSON from table_questions_list.json using local Ollama.

Input (default): table_questions_list.json
  [
    { "text": "..." },
    { "text": "..." },
    ...
  ]

Output (default): intent_training_data_from_table_questions.json
  {
    "version": 1,
    "updated_at": "2025-12-25T00:00:00.000000+00:00",
    "examples": [
      { "text": "...", "intent": "action" },
      { "text": "...", "intent": "informational" },
      ...
    ]
  }

Intent labels:
  - informational
  - action
  - troubleshooting

Classification rules and DB-table trigger logic match your existing
train_intent_classifier Ollama setup.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


DEFAULT_INPUT_PATH = Path("table_questions_list.json")
DEFAULT_OUTPUT_PATH = Path("intent_training_data_from_table_questions.json")


# ------------------------ Utilities ------------------------ #


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().split())


def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)


def _print_block(title: str, body: str) -> None:
    print(f"\n{'=' * 10} {title} {'=' * 10}")
    print(body)
    print(f"{'=' * (22 + len(title))}\n")


def load_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception as e:
        raise SystemExit(f"Failed to read/parse JSON at {path}: {e}") from e


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[write] Saved JSON to: {path.resolve()}")


# ------------------------ LLM helpers ------------------------ #


def _call_local_chat_completions(
    prompt: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> Tuple[str, Dict[str, Any], str, Dict[str, Any]]:
    """
    Calls an OpenAI-compatible /v1/chat/completions endpoint (e.g. Ollama)
    and returns:
      - assistant content string (choices[0].message.content)
      - parsed response JSON envelope (full)
      - raw response text (string)
      - request JSON payload (dict)
    """
    system_prompt = (
        "You are an intent classifier for user queries related to K-12 school systems "
        "and technical/devops tasks.\n\n"
        "You MUST classify each user query into EXACTLY ONE of these labels:\n"
        "- informational\n"
        "- action\n"
        "- troubleshooting\n\n"
        "CRITICAL LABELING RULES:\n"
        "1. If a user query asks to list, show, search, filter, count, query, "
        "   create, update, or delete records from ANY OSSS database table, "
        "   the label MUST be 'action'.\n"
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
        "meeting_files, meeting_permissions, meeting_publications, meeting_search_index, "
        "meetings, memberships, message_recipients, messages, meters, minutes, motions, "
        "move_orders, notifications, nurse_visits, objectives, order_line_items, orders, "
        "organizations, pages, part_locations, parts, pay_periods, paychecks, payments, "
        "payroll_runs, periods, permissions, person_addresses, person_contacts, "
        "personal_notes, persons, plan_alignments, plan_assignments, plan_filters, "
        "plan_search_index, plans, pm_plans, pm_work_generators, policies, "
        "policy_approvals, policy_comments, policy_files, policy_legal_refs, "
        "policy_publications, policy_search_index, policy_versions, "
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
        "OUTPUT FORMAT (STRICT):\n"
        "- Return ONLY valid JSON and NOTHING ELSE.\n"
        "- The JSON MUST be a single object like: {\"intent\": \"action\"}\n"
        "- 'intent' MUST be exactly one of: informational, action, troubleshooting."
    )

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
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
        raise SystemExit(
            f"LLM response missing choices[0].message.content: {e}\nRaw:\n{raw}"
        )

    return str(content), obj, raw, payload


def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """
    Extract one or more top-level JSON objects from a string.
    Handles cases where the model returns multiple JSON objects back-to-back.
    """
    s = text.strip()
    objs: List[Dict[str, Any]] = []

    # Fast path: try single JSON
    try:
        one = json.loads(s)
        if isinstance(one, dict):
            return [one]
        return []
    except json.JSONDecodeError:
        pass

    # Slow path: scan for balanced {...}
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


def classify_intent_for_text(
    text: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> Optional[str]:
    """
    Ask Ollama to classify a single text into an intent.
    Returns one of: 'informational', 'action', 'troubleshooting', or None on failure.
    """
    user_prompt = f"Classify the following user query and return ONLY JSON:\n\n{text}"

    content, _envelope, _raw, _payload = _call_local_chat_completions(
        prompt=user_prompt,
        endpoint=endpoint,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        trace_llm=trace_llm,
        trace_llm_max_chars=trace_llm_max_chars,
    )

    objs = _extract_json_objects(content)
    if not objs:
        print(f"[warn] No JSON object parsed for text={text!r}; content was:\n{content}\n")
        return None

    obj = objs[0]
    intent = obj.get("intent")
    if not isinstance(intent, str):
        print(f"[warn] Invalid 'intent' in LLM output for text={text!r}: {obj!r}")
        return None

    intent_norm = normalize_text(intent).lower()
    if intent_norm not in {"informational", "action", "troubleshooting"}:
        print(
            f"[warn] LLM returned invalid intent '{intent_norm}' "
            f"for text={text!r}; obj={obj!r}"
        )
        return None

    return intent_norm


# ------------------------ CLI / main ------------------------ #


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build training_data-style JSON from table_questions_list.json using local Ollama."
    )
    p.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help=f"Path to input JSON (default: {DEFAULT_INPUT_PATH})",
    )
    p.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Path to output JSON (default: {DEFAULT_OUTPUT_PATH})",
    )
    p.add_argument(
        "--llm-endpoint",
        default="http://localhost:11434/v1/chat/completions",
        help="Chat completions endpoint (default: http://localhost:11434/v1/chat/completions for Ollama)",
    )
    p.add_argument(
        "--llm-model",
        default="llama3.1",
        help="Model name to use at the endpoint (default: llama3.1)",
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
        default=0.0,
        help="Temperature for generation (default: 0.0 for deterministic classification)",
    )
    p.add_argument(
        "--llm-max-tokens",
        type=int,
        default=256,
        help="Max tokens for LLM response (default: 256)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If > 0, only process the first N questions.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="If set, recompute intent even if an 'intent' field already exists in the input.",
    )
    p.add_argument(
        "--trace-llm",
        action="store_true",
        help="Print LLM request/response JSON to stdout.",
    )
    p.add_argument(
        "--trace-llm-max-chars",
        type=int,
        default=4000,
        help="Max chars for LLM raw response/content blocks (default: 4000; 0 = no limit).",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    print(f"[load] input questions: {input_path.resolve()}")
    questions = load_json(input_path)

    if not isinstance(questions, list):
        raise SystemExit(f"Input JSON must be a list of objects: {input_path}")

    limit = int(args.limit) if args.limit and args.limit > 0 else None
    total = len(questions)
    to_process = total if limit is None else min(limit, total)
    print(f"[info] questions total={total}, will process={to_process}")

    examples: List[Dict[str, Any]] = []
    processed = 0
    classified = 0
    defaulted = 0

    for idx, q in enumerate(questions):
        if limit is not None and processed >= limit:
            break

        if not isinstance(q, dict):
            print(f"[warn] index={idx} is not an object; skipping")
            processed += 1
            continue

        text = normalize_text(str(q.get("text", "")))
        if not text:
            print(f"[warn] index={idx} has empty or missing 'text'; skipping")
            processed += 1
            continue

        existing_intent = q.get("intent")
        if isinstance(existing_intent, str) and not args.overwrite:
            intent_norm = normalize_text(existing_intent).lower()
            print(
                f"[keep] index={idx}: already has intent={intent_norm!r}; "
                f"use --overwrite to recompute"
            )
            examples.append({"text": text, "intent": intent_norm})
            processed += 1
            continue

        print(f"[classify] index={idx+1}/{to_process} text={text!r}")

        intent = classify_intent_for_text(
            text,
            endpoint=str(args.llm_endpoint),
            model=str(args.llm_model),
            timeout_seconds=float(args.llm_timeout),
            temperature=float(args.llm_temperature),
            max_tokens=int(args.llm_max_tokens),
            trace_llm=bool(args.trace_llm),
            trace_llm_max_chars=int(args.trace_llm_max_chars),
        )

        if intent is None:
            print(f"[warn] index={idx}: classification failed; defaulting to 'informational'")
            intent = "informational"
            defaulted += 1
        else:
            classified += 1

        examples.append({"text": text, "intent": intent})
        processed += 1

    print(
        f"[summary] processed={processed} classified={classified} "
        f"defaulted={defaulted} (total questions={total})"
    )

    out_obj: Dict[str, Any] = {
        "version": 1,
        "updated_at": utc_now_iso(),
        "examples": examples,
    }

    save_json(output_path, out_obj)


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
