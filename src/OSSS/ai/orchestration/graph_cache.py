"""
Graph compilation caching for OSSS LangGraph backend.

This module provides caching functionality for compiled StateGraphs to improve
performance by avoiding repeated graph compilation for the same configurations.
"""

from __future__ import annotations

import hashlib
import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import OrderedDict
from collections.abc import Mapping

from OSSS.ai.observability import get_logger


@dataclass
class CacheConfig:
    """Configuration for graph caching."""

    max_size: int = 50  # Maximum number of cached graphs
    ttl_seconds: int = 3600  # Time to live in seconds (1 hour)
    enable_stats: bool = True  # Whether to track cache statistics


@dataclass
class CacheEntry:
    """Entry in the graph cache."""

    compiled_graph: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    size_estimate: int = 0  # Estimated memory size in bytes

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if this cache entry has expired."""
        return time.time() - self.created_at > ttl_seconds

    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_evictions: int = 0
    size_evictions: int = 0
    current_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.hits + self.misses


class GraphCache:
    """
    LRU cache for compiled StateGraphs with TTL and size management.

    This cache stores compiled graphs to avoid repeated compilation overhead.
    It supports:
    - LRU eviction policy
    - TTL-based expiration
    - Size-based eviction
    - Thread-safe operations
    - Performance statistics
    """

    DEFAULT_COMPILE_VARIANT = "default"

    def __init__(self, config: Optional[CacheConfig] = None) -> None:
        """
        Initialize the graph cache.

        Parameters
        ----------
        config : CacheConfig, optional
            Cache configuration. If None, default config is used.
        """
        self.config = config or CacheConfig()
        self.logger = get_logger(f"{__name__}.GraphCache")

        # Thread-safe ordered dictionary for LRU behavior
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics tracking
        self._stats = CacheStats(max_size=self.config.max_size)

        self.logger.info(
            f"GraphCache initialized with max_size={self.config.max_size}, "
            f"ttl={self.config.ttl_seconds}s"
        )

    # ---------------------------------------------------------------------
    # Config/dict-safe extraction helpers
    # ---------------------------------------------------------------------
    def _extract_pattern_name(self, cfg: Any, fallback: str = "standard") -> str:
        if isinstance(cfg, Mapping):
            return str(cfg.get("pattern_name") or cfg.get("graph_pattern") or fallback)
        return str(getattr(cfg, "pattern_name", getattr(cfg, "graph_pattern", fallback)))

    def _extract_compile_variant(self, cfg: Any, fallback: str = DEFAULT_COMPILE_VARIANT) -> str:
        """
        Extract compile strategy label (PR4) from GraphConfig-like object OR dict.

        This is NOT a pattern name. It must be included in cache identity so that
        different compile strategies cannot collide.
        """
        if isinstance(cfg, Mapping):
            v = cfg.get("compile_variant") or cfg.get("compile_strategy") or fallback
        else:
            v = getattr(cfg, "compile_variant", None) or getattr(cfg, "compile_strategy", None) or fallback
        s = str(v).strip().lower()
        return s or str(fallback).strip().lower() or self.DEFAULT_COMPILE_VARIANT

    def _extract_agents(self, cfg: Any) -> List[str]:
        """
        Tries common keys/attrs. This is intentionally forgiving because the
        orchestrator may pass dict-like "execution_config" or a GraphConfig object.
        """
        if isinstance(cfg, Mapping):
            raw = (
                cfg.get("agents_to_run")
                or cfg.get("agents")
                or cfg.get("planned_agents")
                or cfg.get("caller_agents")
                or []
            )
        else:
            raw = (
                getattr(cfg, "agents_to_run", None)
                or getattr(cfg, "agents", None)
                or getattr(cfg, "planned_agents", None)
                or getattr(cfg, "caller_agents", None)
                or []
            )

        if raw is None:
            return []

        if isinstance(raw, (list, tuple)):
            return [str(a) for a in raw if str(a).strip()]

        # single string, etc.
        s = str(raw).strip()
        return [s] if s else []

    def _extract_checkpoints_enabled(self, cfg: Any, fallback: bool = False) -> bool:
        if isinstance(cfg, Mapping):
            val = cfg.get("checkpoints_enabled")
            if val is None:
                val = cfg.get("enable_checkpoints")
            return bool(fallback if val is None else val)
        val = getattr(cfg, "checkpoints_enabled", None)
        if val is None:
            val = getattr(cfg, "enable_checkpoints", None)
        return bool(fallback if val is None else val)

    def _extract_version(self, cfg: Any) -> Optional[str]:
        if isinstance(cfg, Mapping):
            v = cfg.get("version") or cfg.get("graph_version") or cfg.get("patterns_version")
            return str(v).strip() if v else None
        v = (
            getattr(cfg, "version", None)
            or getattr(cfg, "graph_version", None)
            or getattr(cfg, "patterns_version", None)
        )
        return str(v).strip() if v else None

    # ---------------------------------------------------------------------
    # Key generation
    # ---------------------------------------------------------------------
    def _generate_cache_key(
        self,
        pattern_name: str,
        agents: List[str],
        checkpoints_enabled: bool,
        version: Optional[str] = None,
        *,
        compile_variant: str = DEFAULT_COMPILE_VARIANT,
    ) -> str:
        # Sort agents for consistent ordering
        sorted_agents = sorted(agent.lower() for agent in agents)

        # Normalize version (keep stable string)
        v = (version or "v0").strip()

        # Normalize variant (must participate in cache identity)
        variant = (compile_variant or self.DEFAULT_COMPILE_VARIANT).strip().lower()

        # Include version + variant in key components
        key_data = f"{v}:{pattern_name}:{variant}:{':'.join(sorted_agents)}:{checkpoints_enabled}"

        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        # Include version prefix for readability/debug
        safe_v = v.replace(":", "_").replace("/", "_")
        safe_variant = variant.replace(":", "_").replace("/", "_")
        return f"{safe_v}_{pattern_name}_{safe_variant}_{key_hash[:8]}"

    def make_cache_key_from_config(self, cfg: Any) -> str:
        """
        Build a cache key from a GraphConfig-like object OR a dict.

        This prevents failures like:
          'dict' object has no attribute 'agents_to_run'
        """
        pattern_name = self._extract_pattern_name(cfg, fallback="standard")
        agents = self._extract_agents(cfg)
        checkpoints_enabled = self._extract_checkpoints_enabled(cfg, fallback=False)
        version = self._extract_version(cfg)
        compile_variant = self._extract_compile_variant(cfg, fallback=self.DEFAULT_COMPILE_VARIANT)
        return self._generate_cache_key(
            pattern_name,
            agents,
            checkpoints_enabled,
            version=version,
            compile_variant=compile_variant,
        )

    # ---------------------------------------------------------------------
    # Existing API (pattern_name/agents/checkpoints)
    # ---------------------------------------------------------------------
    def get_cached_graph(
        self,
        pattern_name: str,
        agents: List[str],
        checkpoints_enabled: bool,
        version: Optional[str] = None,
        *,
        compile_variant: str = DEFAULT_COMPILE_VARIANT,
    ) -> Optional[Any]:
        """
        Retrieve a cached compiled graph.
        """
        cache_key = self._generate_cache_key(
            pattern_name,
            agents,
            checkpoints_enabled,
            version=version,
            compile_variant=compile_variant,
        )

        with self._lock:
            if cache_key not in self._cache:
                self._stats.misses += 1
                self.logger.debug(f"Cache miss for key: {cache_key}")
                return None

            entry = self._cache[cache_key]

            if entry.is_expired(self.config.ttl_seconds):
                self.logger.debug(f"Cache entry expired for key: {cache_key}")
                del self._cache[cache_key]
                self._stats.misses += 1
                self._stats.expired_evictions += 1
                self._stats.current_size = max(0, self._stats.current_size - 1)
                return None

            self._cache.move_to_end(cache_key)
            entry.touch()

            self._stats.hits += 1
            self.logger.debug(f"Cache hit for key: {cache_key}")

            return entry.compiled_graph

    def cache_graph(
        self,
        pattern_name: str,
        agents: List[str],
        checkpoints_enabled: bool,
        compiled_graph: Any,
        version: Optional[str] = None,
        *,
        compile_variant: str = DEFAULT_COMPILE_VARIANT,
    ) -> None:
        """
        Cache a compiled graph.
        """
        cache_key = self._generate_cache_key(
            pattern_name,
            agents,
            checkpoints_enabled,
            version=version,
            compile_variant=compile_variant,
        )

        with self._lock:
            self._cleanup_expired()

            # If replacing an existing key, do not increment size stats
            replacing = cache_key in self._cache

            if not replacing and len(self._cache) >= self.config.max_size:
                self._evict_lru()

            now = time.time()
            entry = CacheEntry(
                compiled_graph=compiled_graph,
                created_at=now,
                last_accessed=now,
                access_count=1,
                size_estimate=self._estimate_graph_size(compiled_graph),
            )

            self._cache[cache_key] = entry
            self._cache.move_to_end(cache_key)

            if not replacing:
                self._stats.current_size += 1

            self.logger.debug(f"Cached graph for key: {cache_key}")

    # ---------------------------------------------------------------------
    # Config/dict-safe convenience API
    # ---------------------------------------------------------------------
    def get_cached_graph_for_config(self, cfg: Any) -> Optional[Any]:
        """
        Retrieve cached graph using a GraphConfig-like object OR dict.

        This is the safest entry point for callers that currently have a config object.
        """
        cache_key = self.make_cache_key_from_config(cfg)

        with self._lock:
            if cache_key not in self._cache:
                self._stats.misses += 1
                self.logger.debug(f"Cache miss for key: {cache_key}")
                return None

            entry = self._cache[cache_key]

            if entry.is_expired(self.config.ttl_seconds):
                self.logger.debug(f"Cache entry expired for key: {cache_key}")
                del self._cache[cache_key]
                self._stats.misses += 1
                self._stats.expired_evictions += 1
                self._stats.current_size = max(0, self._stats.current_size - 1)
                return None

            self._cache.move_to_end(cache_key)
            entry.touch()

            self._stats.hits += 1
            self.logger.debug(f"Cache hit for key: {cache_key}")

            return entry.compiled_graph

    def cache_graph_for_config(self, cfg: Any, compiled_graph: Any) -> None:
        """
        Cache graph using a GraphConfig-like object OR dict.
        """
        pattern_name = self._extract_pattern_name(cfg, fallback="standard")
        agents = self._extract_agents(cfg)
        checkpoints_enabled = self._extract_checkpoints_enabled(cfg, fallback=False)
        version = self._extract_version(cfg)
        compile_variant = self._extract_compile_variant(cfg, fallback=self.DEFAULT_COMPILE_VARIANT)

        self.cache_graph(
            pattern_name=pattern_name,
            agents=agents,
            checkpoints_enabled=checkpoints_enabled,
            compiled_graph=compiled_graph,
            version=version,
            compile_variant=compile_variant,
        )

    # ---------------------------------------------------------------------
    # Housekeeping
    # ---------------------------------------------------------------------
    def _cleanup_expired(self) -> None:
        """Remove expired entries from the cache."""
        expired_keys: List[str] = []
        current_time = time.time()

        for key, entry in list(self._cache.items()):
            if current_time - entry.created_at > self.config.ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            self._stats.expired_evictions += 1
            self._stats.current_size = max(0, self._stats.current_size - 1)
            self.logger.debug(f"Removed expired cache entry: {key}")

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._cache:
            key, _entry = self._cache.popitem(last=False)
            self._stats.evictions += 1
            self._stats.size_evictions += 1
            self._stats.current_size = max(0, self._stats.current_size - 1)
            self.logger.debug(f"Evicted LRU cache entry: {key}")

    def _estimate_graph_size(self, compiled_graph: Any) -> int:
        """Estimate the memory size of a compiled graph."""
        try:
            import sys

            return sys.getsizeof(compiled_graph)
        except Exception:
            return 1024  # 1KB default estimate

    def clear(self) -> None:
        """Clear all cached graphs."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            self._stats.current_size = 0
            self.logger.info(f"Cleared {cleared_count} cached graphs")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "hit_rate": self._stats.hit_rate,
                "total_requests": self._stats.total_requests,
                "current_size": self._stats.current_size,
                "max_size": self._stats.max_size,
                "evictions": self._stats.evictions,
                "expired_evictions": self._stats.expired_evictions,
                "size_evictions": self._stats.size_evictions,
                "ttl_seconds": self.config.ttl_seconds,
                "oldest_entry_age": self._get_oldest_entry_age(),
                "newest_entry_age": self._get_newest_entry_age(),
                "total_access_count": self._get_total_access_count(),
            }

    def _get_oldest_entry_age(self) -> Optional[float]:
        """Get age of oldest cache entry in seconds."""
        if not self._cache:
            return None
        current_time = time.time()
        oldest_entry = next(iter(self._cache.values()))
        return current_time - oldest_entry.created_at

    def _get_newest_entry_age(self) -> Optional[float]:
        """Get age of newest cache entry in seconds."""
        if not self._cache:
            return None
        current_time = time.time()
        newest_entry = next(reversed(self._cache.values()))
        return current_time - newest_entry.created_at

    def _get_total_access_count(self) -> int:
        """Get total access count across all entries."""
        return sum(entry.access_count for entry in self._cache.values())

    def get_cache_keys(self) -> List[str]:
        """Get all current cache keys."""
        with self._lock:
            return list(self._cache.keys())

    def remove_pattern(self, pattern_name: str, version: Optional[str] = None) -> int:
        """
        Remove cached graphs for a specific pattern.

        - If version is provided: remove only that version for the pattern.
        - If version is None: remove all versions (and legacy keys) for the pattern.
        """
        pat = (pattern_name or "").strip()
        if not pat:
            return 0

        def safe_version(v: str) -> str:
            return (v or "v0").strip().replace(":", "_").replace("/", "_")

        removed_count = 0

        with self._lock:
            keys = list(self._cache.keys())

            if version:
                sv = safe_version(version)
                prefix = f"{sv}_{pat}_"
                keys_to_remove = [k for k in keys if k.startswith(prefix)]
            else:
                needle = f"_{pat}_"
                keys_to_remove = [k for k in keys if k.startswith(f"{pat}_") or needle in k]

            for k in keys_to_remove:
                del self._cache[k]
                self._stats.current_size = max(0, self._stats.current_size - 1)
                removed_count += 1

            if removed_count > 0:
                if version:
                    self.logger.info(
                        f"Removed {removed_count} cached graphs for pattern='{pat}' version='{safe_version(version)}'"
                    )
                else:
                    self.logger.info(f"Removed {removed_count} cached graphs for pattern='{pat}' (all versions)")

            return removed_count

    def optimize(self) -> Dict[str, Any]:
        """
        Optimize the cache by removing expired entries and defragmenting.

        Returns
        -------
        Dict[str, int]
            Optimization statistics
        """
        with self._lock:
            initial_size = len(self._cache)

            self._cleanup_expired()

            final_size = len(self._cache)
            removed = initial_size - final_size

            self.logger.info(f"Cache optimization removed {removed} entries")

            return {
                "initial_size": initial_size,
                "final_size": final_size,
                "removed_entries": removed,
                "current_hit_rate": self._stats.hit_rate,
            }
