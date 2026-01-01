#!/usr/bin/env python3
"""
Train classifiers for intent, domain, and topics from JSON training data.

Input JSON formats supported:

1) Dict with "examples":
   {
     "version": 1,
     "updated_at": "...",
     "examples": [
       {
         "text": "How do I create a new user role in the OSSS admin app?",
         "intent": "action",
         "domain": "data_systems",
         "topics": ["role_permissions", "roles"]
       },
       ...
     ]
   }

2) Plain list of examples:
   [
     {
       "text": "...",
       "intent": "...",
       "domain": "...",
       "topics": ["...", "..."]
     },
     ...
   ]

Output:
- A single joblib bundle with:
    - vectorizer
    - domain_clf, domain_le
    - intent_clf, intent_le
    - topics_clf, topic_mlb

Usage:
  ./train_intent_domain_topic_classifier.py \
      --data training_data.json \
      --out models/domain_topic_intent_classifier.joblib
"""

from __future__ import annotations

from pathlib import Path
import argparse
import json
from typing import Any, Dict, List, Tuple

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, MultiLabelBinarizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import classification_report


DEFAULT_DATA_PATH = Path("data") / "training_data2.json"
DEFAULT_MODEL_PATH = Path("models") / "domain_topic_intent_classifier.joblib"


# ------------------------ Utilities ------------------------ #

def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().split())


def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)


# ------------------------ Data loading ------------------------ #

def load_examples(path: Path) -> List[Dict[str, Any]]:
    """Load training examples from JSON file."""
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as e:
        raise SystemExit(f"Failed to read/parse training JSON at {path}: {e}") from e

    if isinstance(data, dict):
        examples = data.get("examples")
        if not isinstance(examples, list):
            raise SystemExit(f"When top-level is an object, it must have 'examples' as a list: {path}")
    elif isinstance(data, list):
        examples = data
    else:
        raise SystemExit(f"Training JSON must be either a list or an object with 'examples': {path}")

    cleaned: List[Dict[str, Any]] = []
    for ex in examples:
        if not isinstance(ex, dict):
            continue
        text = normalize_text(str(ex.get("text", "")))
        intent = normalize_text(str(ex.get("intent", ""))).lower()
        domain = normalize_text(str(ex.get("domain", ""))).lower()
        topics_raw = ex.get("topics", [])

        if not text or not intent or not domain:
            # Require at least text, intent, and domain
            continue

        if isinstance(topics_raw, list):
            topics = [normalize_text(str(t)) for t in topics_raw if normalize_text(str(t))]
        elif isinstance(topics_raw, str) and topics_raw.strip():
            topics = [normalize_text(topics_raw)]
        else:
            topics = []

        cleaned.append(
            {
                "text": text,
                "intent": intent,
                "domain": domain,
                "topics": topics,
            }
        )

    if not cleaned:
        raise SystemExit("No valid examples found in training JSON.")
    return cleaned


def to_arrays(
    examples: List[Dict[str, Any]]
) -> Tuple[List[str], List[str], List[List[str]], List[str]]:
    """Split examples into separate label arrays."""
    texts: List[str] = []
    domains: List[str] = []
    topics_list: List[List[str]] = []
    intents: List[str] = []

    for ex in examples:
        texts.append(ex["text"])
        domains.append(ex["domain"])
        topics_list.append(ex["topics"])
        intents.append(ex["intent"])

    return texts, domains, topics_list, intents


# ------------------------ Training ------------------------ #

def train_models(
    texts: List[str],
    domains: List[str],
    topics_list: List[List[str]],
    intents: List[str],
) -> Dict[str, Any]:
    """
    Train:
      - intent classifier (single label)
      - domain classifier (single label)
      - topics classifier (multi-label)
    All share the same TF-IDF vectorizer.
    """
    print(f"[data] n_examples={len(texts)}")

    # Vectorizer (shared)
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    X = vectorizer.fit_transform(texts)
    print(f"[vectorizer] vocab_size={len(vectorizer.vocabulary_)}")

    # Domain encoder + classifier
    domain_le = LabelEncoder()
    y_domain = domain_le.fit_transform(domains)
    domain_clf = LogisticRegression(max_iter=2000)
    domain_clf.fit(X, y_domain)
    print(f"[train] trained domain classifier on {len(domain_le.classes_)} classes")

    # Intent encoder + classifier
    intent_le = LabelEncoder()
    y_intent = intent_le.fit_transform(intents)
    intent_clf = LogisticRegression(max_iter=2000)
    intent_clf.fit(X, y_intent)
    print(f"[train] trained intent classifier on {len(intent_le.classes_)} classes")

    # Topics multi-label classifier
    topic_mlb = MultiLabelBinarizer()
    y_topics = topic_mlb.fit_transform(topics_list)
    topics_clf = OneVsRestClassifier(LogisticRegression(max_iter=2000))
    topics_clf.fit(X, y_topics)
    print(f"[train] trained topics classifier on {len(topic_mlb.classes_)} possible topics")

    # Optional: quick reports (can be commented out if noisy)
    print("\n[classification_report] Domain:")
    print(classification_report(y_domain, domain_clf.predict(X), target_names=domain_le.classes_))

    print("\n[classification_report] Intent:")
    print(classification_report(y_intent, intent_clf.predict(X), target_names=intent_le.classes_))

    # Bundle everything
    bundle: Dict[str, Any] = {
        "vectorizer": vectorizer,
        "domain_clf": domain_clf,
        "domain_le": domain_le,
        "intent_clf": intent_clf,
        "intent_le": intent_le,
        "topics_clf": topics_clf,
        "topic_mlb": topic_mlb,
    }
    return bundle


def save_bundle(bundle: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)
    print(f"[model] Saved model bundle to: {out_path.resolve()}")


# ------------------------ Inference helper ------------------------ #

def classify_sample(bundle: Dict[str, Any], text: str) -> Dict[str, Any]:
    """Convenience helper to test the trained bundle on a single text."""
    v = bundle["vectorizer"]
    X = v.transform([normalize_text(text)])

    domain_clf = bundle["domain_clf"]
    domain_le = bundle["domain_le"]
    intent_clf = bundle["intent_clf"]
    intent_le = bundle["intent_le"]
    topics_clf = bundle["topics_clf"]
    topic_mlb = bundle["topic_mlb"]

    # Domain
    domain_proba = domain_clf.predict_proba(X)[0]
    domain_idx = domain_proba.argmax()
    domain = domain_le.inverse_transform([domain_idx])[0]
    domain_conf = float(domain_proba[domain_idx])

    # Intent
    intent_proba = intent_clf.predict_proba(X)[0]
    intent_idx = intent_proba.argmax()
    intent = intent_le.inverse_transform([intent_idx])[0]
    intent_conf = float(intent_proba[intent_idx])

    # Topics (multi-label)
    topics_proba = topics_clf.predict_proba(X)[0]
    topic_names = list(topic_mlb.classes_)
    # simple threshold; you can tune this
    threshold = 0.3
    topics = [
        (topic_names[i], float(p))
        for i, p in enumerate(topics_proba)
        if p >= threshold
    ]
    topics_sorted = sorted(topics, key=lambda t: t[1], reverse=True)

    return {
        "text": text,
        "intent": intent,
        "intent_confidence": intent_conf,
        "domain": domain,
        "domain_confidence": domain_conf,
        "topics": [t for t, _ in topics_sorted],
        "topics_confidences": {t: c for t, c in topics_sorted},
    }


# ------------------------ CLI / main ------------------------ #

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train intent+domain+topics classifiers from JSON training data."
    )
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
        "--test-text",
        default="How do I create a new user role in the OSSS admin app?",
        help="Optional sample text to classify after training.",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    data_path = Path(args.data)
    out_path = Path(args.out)

    print(f"[load] training data: {data_path.resolve()}")
    examples = load_examples(data_path)
    texts, domains, topics_list, intents = to_arrays(examples)

    bundle = train_models(texts, domains, topics_list, intents)
    save_bundle(bundle, out_path)

    # Quick sanity check on one sample
    print("\n[test] Sample classification:")
    res = classify_sample(bundle, args.test_text)
    print(_pretty_json(res))


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
