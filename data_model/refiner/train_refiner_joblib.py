#!/usr/bin/env python3

import joblib
import pandas as pd
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

    def fit(self, raw_queries: List[str], refined_queries: List[str]) -> "NearestNeighborRefiner":
        if len(raw_queries) != len(refined_queries):
            raise ValueError("raw_queries and refined_queries must have same length")

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
        For compatibility with your RefinerAgent._joblib_refine:

        Returns a list of dicts:
            {
                "refined_query": <str>,
                "confidence": <float 0..1>,
            }
        """
        if self.vectorizer is None or self.nn is None:
            raise RuntimeError("Model not fitted")

        X_q = self.vectorizer.transform(queries)
        distances, indices = self.nn.kneighbors(X_q, n_neighbors=1)

        results: List[Dict[str, Any]] = []

        for i, query in enumerate(queries):
            idx = indices[i, 0]
            dist = float(distances[i, 0])  # cosine distance
            # Convert cosine distance -> similarity
            similarity = 1.0 - dist
            similarity = max(0.0, min(1.0, similarity))

            refined = self.refined_queries[idx]

            results.append(
                {
                    "refined_query": refined,
                    "confidence": similarity,
                    "nearest_training_example": self.raw_queries[idx],
                }
            )

        return results


def main() -> None:
    # 1) Load training data
    df = pd.read_csv("data/refiner_training_data.csv")

    raw_queries = df["raw_query"].astype(str).tolist()
    refined_queries = df["refined_query"].astype(str).tolist()

    # 2) Train the model
    model = NearestNeighborRefiner(n_neighbors=1)
    model.fit(raw_queries, refined_queries)

    # 3) (Optional) quick sanity check
    test_queries = [
        "dcg teachers",
        "show me dcg grades",
        "query dcg consents from database",
    ]
    preds = model.predict(test_queries)
    for q, pred in zip(test_queries, preds):
        print("Q:", q)
        print("  ->", pred)

    # 4) Save via joblib
    joblib.dump(model, "models/refiner_nn.joblib")
    print("Saved model to refiner_nn.joblib")


if __name__ == "__main__":
    main()
