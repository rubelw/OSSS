# src/OSSS/ai/metrics.py
from __future__ import annotations

from typing import Any, Mapping

try:
    from prometheus_client import Counter, Histogram
    _HAS_PROM = True
except Exception:  # pragma: no cover
    # Fallback no-op implementation so code doesn't crash if Prometheus isn't installed
    _HAS_PROM = False

    class _NoOpMetric:
        def labels(self, *_, **__):  # type: ignore[override]
            return self

        def inc(self, *_: Any, **__: Any) -> None:
            pass

        def observe(self, *_: Any, **__: Any) -> None:
            pass

    def Counter(*_, **__):  # type: ignore[misc, override]
        return _NoOpMetric()

    def Histogram(*_, **__):  # type: ignore[misc, override]
        return _NoOpMetric()


# ---- RAG metrics ----

RAG_REQUESTS_TOTAL = Counter(
    "rag_requests_total",
    "Total number of RAG prefetch requests",
    labelnames=("index", "outcome"),  # outcome=success|error
)

RAG_HITS_TOTAL = Counter(
    "rag_hits_total",
    "Total number of RAG hits returned",
    labelnames=("index",),
)

RAG_PREFETCH_LATENCY_MS = Histogram(
    "rag_prefetch_latency_ms",
    "Total RAG prefetch latency in milliseconds",
    labelnames=("index",),
)

RAG_EMBEDDING_LATENCY_MS = Histogram(
    "rag_embedding_latency_ms",
    "Embedding call latency in milliseconds",
    labelnames=("model",),
)

RAG_SEARCH_LATENCY_MS = Histogram(
    "rag_search_latency_ms",
    "Vector search latency in milliseconds",
    labelnames=("index",),
)


def observe_prefetch(
    *,
    index: str,
    outcome: str,
    hits: int,
    elapsed_ms_total: float,
    elapsed_ms_embed: float | None,
    elapsed_ms_search: float,
    embed_model: str,
) -> None:
    """
    One helper to update all RAG metrics in a consistent way.
    Safe to call even if Prometheus is not installed (becomes no-op).
    """
    # Counter for requests
    RAG_REQUESTS_TOTAL.labels(index=index, outcome=outcome).inc()

    # Hits counter (we increment by hits so you can sum over time)
    if hits > 0:
        RAG_HITS_TOTAL.labels(index=index).inc(hits)

    # Latencies
    RAG_PREFETCH_LATENCY_MS.labels(index=index).observe(elapsed_ms_total)
    RAG_SEARCH_LATENCY_MS.labels(index=index).observe(elapsed_ms_search)

    if elapsed_ms_embed is not None:
        RAG_EMBEDDING_LATENCY_MS.labels(model=embed_model).observe(elapsed_ms_embed)
