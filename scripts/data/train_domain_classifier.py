#!/usr/bin/env python3
"""
Train a domain classifier using transformer embeddings + scikit-learn,
similar to the Newscatcher "Transformers & scikit-learn" tutorial.

- Input: training_data.json
    {
      "version": 1,
      "updated_at": "...",
      "examples": [
        {
          "text": "List the DCG School Board Members",
          "intent": "informational",     # can be present but ignored
          "domain": "governance_board",  # REQUIRED for training
          "topics": ["board_members"]    # optional, ignored here
        },
        ...
      ]
    }

- Output:
    models/domain_classifier.joblib  (contains label encoder + sklearn classifier)

Usage:
    ./train_domain_classifier.py
    ./train_domain_classifier.py --data training_data.json --out models/domain_classifier.joblib
"""

from __future__ import annotations

from pathlib import Path
import argparse
import json
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, accuracy_score
import joblib

from sentence_transformers import SentenceTransformer


DEFAULT_DATA_PATH = Path("training_data.json")
DEFAULT_MODEL_PATH = Path("models") / "domain_classifier.joblib"
DEFAULT_SENTENCE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ------------------------ Utilities ------------------------ #

def load_training_json(path: Path) -> Dict[str, Any]:
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


def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().split())


def extract_texts_and_labels(
    data: Dict[str, Any],
    label_field: str = "domain",
) -> Tuple[List[str], List[str]]:
    """
    Extract (text, label) pairs from training_data.json.

    Skips any example missing the label_field.
    """
    examples = data.get("examples", [])
    texts: List[str] = []
    labels: List[str] = []

    for ex in examples:
        if not isinstance(ex, dict):
            continue
        text = normalize_text(str(ex.get("text", "")))
        label = ex.get(label_field)

        if not text or not isinstance(label, str) or not label.strip():
            continue

        texts.append(text)
        labels.append(label.strip())

    if not texts:
        raise SystemExit(
            f"No usable examples found with non-empty 'text' and '{label_field}'"
        )

    print(f"[data] extracted {len(texts)} (text, {label_field}) pairs")
    return texts, labels


# ------------------------ Training logic ------------------------ #

def train_domain_classifier(
    texts: List[str],
    labels: List[str],
    *,
    sentence_model_name: str,
    test_size: float,
    random_state: int,
) -> Dict[str, Any]:
    """
    - Computes sentence embeddings using SentenceTransformer.
    - Trains a LinearSVC classifier on embeddings.
    - Returns a dict containing:
        {
          "sentence_model_name": ...,
          "label_encoder": LabelEncoder,
          "classifier": fitted sklearn classifier
        }
    """
    print(f"[embed] loading sentence transformer model: {sentence_model_name!r}")
    sent_model = SentenceTransformer(sentence_model_name)

    print(f"[embed] encoding {len(texts)} texts...")
    X = sent_model.encode(texts, show_progress_bar=True)
    X = np.asarray(X, dtype="float32")

    # encode labels to integers
    le = LabelEncoder()
    y = le.fit_transform(labels)

    print("[split] creating train/test split...")
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    print(
        f"[train] training LinearSVC on {X_train.shape[0]} examples "
        f"(test={X_test.shape[0]})"
    )
    clf = LinearSVC()
    clf.fit(X_train, y_train)

    print("[eval] evaluating on test set...")
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"[eval] accuracy: {acc:.4f}\n")

    print("[eval] classification report:")
    target_names = le.inverse_transform(sorted(set(y_test)))
    # classification_report expects names in label index order; handle robustly:
    print(
        classification_report(
            y_test,
            y_pred,
            labels=sorted(set(y_test)),
            target_names=[le.inverse_transform([i])[0] for i in sorted(set(y_test))],
            digits=4,
        )
    )

    model_bundle = {
        "sentence_model_name": sentence_model_name,
        "label_encoder": le,
        "classifier": clf,
    }
    return model_bundle


# ------------------------ CLI ------------------------ #

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train a domain classifier from training_data.json using transformer embeddings + scikit-learn."
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
        "--label-field",
        default="domain",
        help="Field name to use as the label in examples (default: domain).",
    )
    p.add_argument(
        "--sentence-model",
        default=DEFAULT_SENTENCE_MODEL,
        help=f"SentenceTransformer model name (default: {DEFAULT_SENTENCE_MODEL})",
    )
    p.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of data to use as test set (default: 0.2).",
    )
    p.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for train/test split (default: 42).",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    data_path = Path(args.data)
    out_path = Path(args.out)

    print(f"[load] training data: {data_path.resolve()}")
    data = load_training_json(data_path)

    texts, labels = extract_texts_and_labels(data, label_field=args.label_field)

    model_bundle = train_domain_classifier(
        texts,
        labels,
        sentence_model_name=args.sentence_model,
        test_size=float(args.test_size),
        random_state=int(args.random_state),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_bundle, out_path)
    print(f"[save] saved domain classifier to: {out_path.resolve()}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
