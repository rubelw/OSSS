#!/usr/bin/env python3
"""
Annotate training_data.json examples with domain and topics using regex first, then local Ollama.

- Reads:
    training_data.json   (with "examples": [{ "text": "...", "intent": "..." }, ...])
    topics.json          (with { "domain_key": ["topic1", "topic2", ...], ... })

- For each example:
    1) Try regex/substring matching against topics.json:
       - Build a dict: domain -> set(matched_topics).
       - If non-empty:
           * Pick domain with most matched topics as primary domain.
           * Use those topics as the topics list.
    2) If no topics matched at all:
       - Call local Ollama (OpenAI-compatible /v1/chat/completions) to classify.

- Writes:
    training_data2.json  (same structure as input, but each example has added:
                          "domain": "<domain_key>",
                          "topics": ["topic1", "topic2", ...])

- NEW:
    * training_data2.json is written AFTER EACH example is processed.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


DEFAULT_DATA_PATH = Path("training_data.json")
DEFAULT_TOPICS_PATH = Path("topics.json")


# ------------------------ Utilities ------------------------ #

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
    print(f"[write] Saved updated JSON to: {path.resolve()}")


# ------------------------ LLM helper ------------------------ #

def _call_local_chat_completions(
    *,
    endpoint: str,
    model: str,
    system_prompt: str,
    user_content: str,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> Tuple[str, Dict[str, Any], str, Dict[str, Any]]:
    """
    Calls a local OpenAI-compatible /v1/chat/completions endpoint and returns:
      - assistant content string (choices[0].message.content)
      - parsed response JSON envelope
      - raw response text
      - request JSON payload
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
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
        raise SystemExit(f"LLM response missing choices[0].message.content: {e}\nRaw:\n{raw}")

    return str(content), obj, raw, payload


def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """
    Extract one or more top-level JSON objects from a string.
    Handles cases where the model returns multiple JSON objects back-to-back.
    """
    s = text.strip()
    objs: List[Dict[str, Any]] = []

    # Fast path
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


# ------------------------ Domain/Topic classification ------------------------ #

def build_system_prompt(domains_to_topics: Dict[str, List[str]]) -> str:
    """
    Build the system prompt describing domains and topics and strict output format.
    """
    lines: List[str] = [
        "You are a classifier for K-12 school district queries.",
        "Your job is to:",
        "1) Choose EXACTLY ONE domain from the list of domain keys.",
        "2) Choose one or more topics from THAT domain's topic list.",
        "",
        "DOMAINS AND TOPICS:",
    ]
    for dom, topics in sorted(domains_to_topics.items()):
        lines.append(f"- {dom}:")
        for t in topics:
            lines.append(f"    - {t}")
    lines.extend(
        [
            "",
            "OUTPUT FORMAT (STRICT):",
            "- Return ONLY valid JSON (no markdown, no extra text).",
            "- The JSON MUST be a single object like:",
            '  {"domain": "<domain_key>", "topics": ["topic1", "topic2"]}',
            "- domain MUST be one of the domain keys listed above.",
            "- topics MUST be a non-empty list of strings, each taken VERBATIM",
            "  from the topics shown for the selected domain.",
        ]
    )
    return "\n".join(lines)


def classify_via_regex(
    *,
    text: str,
    domains_to_topics: Dict[str, List[str]],
) -> Tuple[Optional[str], List[str]]:
    """
    First-pass classifier using regex/substring matches only.

    - For each domain/topic, if the topic string appears in the text (case-insensitive),
      record it.
    - Build a mapping: domain -> set(matched_topics).
    - If the mapping is non-empty:
        * Pick the domain with the most matched topics.
        * Return that domain and its list of matched topics.
    - If mapping is empty: return (None, []), so caller can fall back to LLM.
    """
    text_norm = text.lower()
    domain_to_matches: Dict[str, set[str]] = {}

    for dom, topics in domains_to_topics.items():
        for topic in topics:
            topic_norm = topic.lower()
            if not topic_norm:
                continue

            pattern = re.escape(topic_norm)
            if re.search(pattern, text_norm, flags=re.IGNORECASE):
                domain_to_matches.setdefault(dom, set()).add(topic)

    if not domain_to_matches:
        return None, []

    primary_domain, matched_topics = max(
        domain_to_matches.items(), key=lambda kv: len(kv[1])
    )
    topics_list = sorted(matched_topics)

    return primary_domain, topics_list


def classify_domain_and_topics_via_llm(
    *,
    text: str,
    domains_to_topics: Dict[str, List[str]],
    endpoint: str,
    model: str,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> Tuple[Optional[str], List[str]]:
    """
    Fallback classifier using Ollama / local LLM when regex matching finds nothing.
    """
    system_prompt = build_system_prompt(domains_to_topics)
    user_content = f"User query:\n{text}\n\nReturn ONLY the JSON object as specified."

    content, _envelope, _raw, _payload = _call_local_chat_completions(
        endpoint=endpoint,
        model=model,
        system_prompt=system_prompt,
        user_content=user_content,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        trace_llm=trace_llm,
        trace_llm_max_chars=trace_llm_max_chars,
    )

    objs = _extract_json_objects(content)
    if not objs:
        print(f"[warn] No JSON object parsed for text={text!r}; content was:\n{content}\n")
        return None, []

    obj = objs[0]
    domain = obj.get("domain")
    topics = obj.get("topics")

    if not isinstance(domain, str):
        print(f"[warn] Invalid 'domain' in LLM output for text={text!r}: {obj!r}")
        return None, []

    if domain not in domains_to_topics:
        print(
            f"[warn] LLM returned domain '{domain}' not in topics.json keys; "
            f"text={text!r} | obj={obj!r}"
        )
        return None, []

    if not isinstance(topics, list):
        print(f"[warn] Invalid 'topics' list in LLM output for text={text!r}: {obj!r}")
        return domain, []

    allowed_topics = set(domains_to_topics.get(domain, []))
    cleaned_topics: List[str] = []
    for t in topics:
        if not isinstance(t, str):
            continue
        t_norm = normalize_text(t)
        if t_norm in allowed_topics and t_norm not in cleaned_topics:
            cleaned_topics.append(t_norm)

    if not cleaned_topics:
        print(
            f"[warn] No valid topics matched for domain '{domain}' "
            f"and text={text!r}; original topics={topics!r}"
        )

    return domain, cleaned_topics


def classify_domain_and_topics_for_text(
    *,
    text: str,
    domains_to_topics: Dict[str, List[str]],
    endpoint: str,
    model: str,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    trace_llm: bool,
    trace_llm_max_chars: int,
) -> Tuple[Optional[str], List[str]]:
    """
    Orchestrates classification:
      1) Regex/substring match against topics.json (fast, deterministic).
      2) If no regex matches, call LLM via Ollama.
    """
    domain, topics_list = classify_via_regex(
        text=text,
        domains_to_topics=domains_to_topics,
    )
    if domain is not None:
        print(f"[regex] matched domain={domain!r}, topics={topics_list!r}")
        return domain, topics_list

    print("[regex] no matches; falling back to LLM classification")
    return classify_domain_and_topics_via_llm(
        text=text,
        domains_to_topics=domains_to_topics,
        endpoint=endpoint,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        trace_llm=trace_llm,
        trace_llm_max_chars=trace_llm_max_chars,
    )


# ------------------------ CLI / main ------------------------ #

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Annotate training_data.json with domain/topics using regex first, "
            "then local Ollama, and write incrementally to training_data2.json."
        )
    )
    p.add_argument(
        "--data",
        default=str(DEFAULT_DATA_PATH),
        help=f"Path to training data JSON (default: {DEFAULT_DATA_PATH})",
    )
    p.add_argument(
        "--topics",
        default=str(DEFAULT_TOPICS_PATH),
        help=f"Path to topics JSON (default: {DEFAULT_TOPICS_PATH})",
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
        help="If > 0, only process the first N examples.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run classification but do NOT write changes back to disk.",
    )
    p.add_argument(
        "--trace-llm",
        action="store_true",
        help="Print the exact LLM request JSON and raw response JSON to stdout.",
    )
    p.add_argument(
        "--trace-llm-max-chars",
        type=int,
        default=4000,
        help="Max chars to print for LLM raw response/content blocks (default: 4000). Use 0 for no truncation.",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    data_path = Path(args.data)
    topics_path = Path(args.topics)

    print(f"[load] training data: {data_path.resolve()}")
    print(f"[load] topics:        {topics_path.resolve()}")

    data = load_json(data_path)
    topics = load_json(topics_path)

    if not isinstance(data, dict):
        raise SystemExit(f"training_data.json must be a JSON object at top level: {data_path}")
    if not isinstance(topics, dict):
        raise SystemExit(f"topics.json must be a JSON object at top level: {topics_path}")

    examples = data.get("examples")
    if not isinstance(examples, list):
        raise SystemExit(f"training_data.json must contain 'examples' as a list: {data_path}")

    # Work on a copy so original in memory is untouched
    output_data = deepcopy(data)
    output_examples = output_data.get("examples", [])

    # Output path for incremental writes
    output_path = data_path.parent / "training_data2.json"
    print(f"[info] output will be written incrementally to: {output_path.resolve()}")

    # Force domains_to_topics mapping to dict[str, List[str]]
    domains_to_topics: Dict[str, List[str]] = {}
    for dom, vals in topics.items():
        if not isinstance(dom, str):
            continue
        if not isinstance(vals, list):
            continue
        domains_to_topics[dom] = [normalize_text(str(v)) for v in vals if normalize_text(str(v))]

    if not domains_to_topics:
        raise SystemExit("topics.json did not contain any usable domain/topic mappings.")

    limit = int(args.limit) if args.limit and args.limit > 0 else None

    total = len(output_examples)
    to_process = total if limit is None else min(limit, total)
    print(f"[info] examples total={total}, will process={to_process}")

    processed = 0
    updated = 0
    skipped = 0

    for idx, ex in enumerate(output_examples):
        if limit is not None and processed >= limit:
            break

        if not isinstance(ex, dict):
            print(f"[warn] example index={idx} is not an object; skipping")
            skipped += 1
            processed += 1
            # still save after this iteration so file reflects progress
            if not args.dry_run:
                save_json(output_path, output_data)
            continue

        text = normalize_text(str(ex.get("text", "")))
        if not text:
            print(f"[warn] example index={idx} has empty text; skipping")
            skipped += 1
            processed += 1
            if not args.dry_run:
                save_json(output_path, output_data)
            continue

        print(f"[classify] index={idx+1}/{to_process} text={text!r}")
        domain, topics_list = classify_domain_and_topics_for_text(
            text=text,
            domains_to_topics=domains_to_topics,
            endpoint=str(args.llm_endpoint),
            model=str(args.llm_model),
            timeout_seconds=float(args.llm_timeout),
            temperature=args.llm_temperature,
            max_tokens=args.llm_max_tokens,
            trace_llm=args.trace_llm,
            trace_llm_max_chars=args.trace_llm_max_chars,
        )

        if domain is None:
            print(f"[warn] index={idx}: classification failed; leaving example unchanged")
            skipped += 1
        else:
            ex["domain"] = domain
            ex["topics"] = topics_list  # may be empty if LLM gave no valid topics
            updated += 1
            print(f"[ok] index={idx}: domain={domain!r}, topics={topics_list!r}")

        processed += 1

        # NEW: write after each analysis
        if not args.dry_run:
            save_json(output_path, output_data)

    print(
        f"[summary] processed={processed} updated={updated} skipped={skipped} "
        f"(total examples={total})"
    )

    if args.dry_run:
        print("[info] --dry-run set; no file writes were performed.")


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
