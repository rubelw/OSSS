#!/usr/bin/env python3

from __future__ import annotations

import joblib
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


class NearestNeighborRefiner:
    """
    Simple nearest-neighbor refiner.

    - fit() stores:
        * tfidf vectorizer
        * raw_query embeddings
        * refined_query list
    - predict([query]) returns:
        * dict(refined_query=..., confidence=similarity)
    """

    def __init__(self, n_neighbors: int = 1):
        self.n_neighbors = n_neighbors
        self.vectorizer = None
        self.nn = None
        self.raw_queries: List[str] = []
        self.refined_queries: List[str] = []

    def fit(
        self,
        raw_queries: List[str],
        refined_queries: List[str],
    ) -> "NearestNeighborRefiner":
        if len(raw_queries) != len(refined_queries):
            raise ValueError("raw_queries and refined_queries must have same length")

        if not raw_queries:
            raise ValueError("Training data is empty")

        self.raw_queries = list(raw_queries)
        self.refined_queries = list(refined_queries)

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            lowercase=True,
        )
        X = self.vectorizer.fit_transform(self.raw_queries)

        self.nn = NearestNeighbors(
            n_neighbors=self.n_neighbors,
            metric="cosine",
        )
        self.nn.fit(X)
        return self

    def predict(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Returns:
            {
                "refined_query": <str>,
                "confidence": <float 0..1>,
                "nearest_training_example": <str>,
            }
        """
        if self.vectorizer is None or self.nn is None:
            raise RuntimeError("Model not fitted")

        X_q = self.vectorizer.transform(queries)
        distances, indices = self.nn.kneighbors(X_q, n_neighbors=1)

        results: List[Dict[str, Any]] = []

        for i in range(len(queries)):
            idx = indices[i, 0]
            dist = float(distances[i, 0])  # cosine distance
            similarity = max(0.0, min(1.0, 1.0 - dist))

            results.append(
                {
                    "refined_query": self.refined_queries[idx],
                    "confidence": similarity,
                    "nearest_training_example": self.raw_queries[idx],
                }
            )

        return results


def main() -> None:
    # ------------------------------------------------------------------
    # Resolve paths relative to THIS file (not cwd)
    # ------------------------------------------------------------------
    script_dir = Path(__file__).resolve().parent
    data_csv = script_dir / "data" / "refiner_training_data.csv"
    model_dir = script_dir / "models"
    model_path = model_dir / "refiner_nn.joblib"

    if not data_csv.exists():
        raise FileNotFoundError(f"Training CSV not found: {data_csv}")

    # ------------------------------------------------------------------
    # Load training data
    # ------------------------------------------------------------------
    df = pd.read_csv(data_csv)

    required_cols = {"raw_query", "refined_query"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    raw_queries = df["raw_query"].astype(str).tolist()
    refined_queries = df["refined_query"].astype(str).tolist()

    print(f"Loaded {len(raw_queries)} training examples from {data_csv}")

    # ------------------------------------------------------------------
    # Train model
    # ------------------------------------------------------------------
    model = NearestNeighborRefiner(n_neighbors=1)
    model.fit(raw_queries, refined_queries)

    # ------------------------------------------------------------------
    # Sanity check
    # ------------------------------------------------------------------
    test_queries = [
        "dcg teachers",
        "show me dcg grades",
        "query dcg consents from database",
    ]

    print("\nSanity check:")
    preds = model.predict(test_queries)
    for q, pred in zip(test_queries, preds):
        print(f"Q: {q}")
        print(f"  -> {pred}")

    # ------------------------------------------------------------------
    # Save model
    # ------------------------------------------------------------------
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    print(f"\nSaved model to {model_path}")


if __name__ == "__main__":
    main()
