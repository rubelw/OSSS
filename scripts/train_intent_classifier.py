#!/usr/bin/env python3
"""
Train a simple intent classifier and save it to models/intent_classifier.joblib.

This is intentionally lightweight:
- TF-IDF + Linear classifier (LogReg) works well for short queries
- You can expand labels & examples over time
"""

from __future__ import annotations

from pathlib import Path
import joblib

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


# You can start small and expand this dataset as you collect real queries.
# Labels should match what your OSSS code expects (e.g. "informational", "action", etc.).
TRAINING_DATA: list[tuple[str, str]] = [
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


def main() -> None:
    texts = [t for t, _ in TRAINING_DATA]
    labels = [y for _, y in TRAINING_DATA]

    pipeline = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=2000)),
        ]
    )

    pipeline.fit(texts, labels)

    out_path = Path("models") / "intent_classifier.joblib"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(pipeline, out_path)
    print(f"Saved model to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
