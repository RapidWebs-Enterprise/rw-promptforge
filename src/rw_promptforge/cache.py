"""File-backed LRU cache for text embeddings.

Cache lives in XDG-compliant location (~/.cache/rw-promptforge/embeddings.pkl)
unless overridden. Embeddings are deterministic functions of (model, text) so
no TTL is applied — entries evicted only on capacity via LRU.

See ADR-011 for rationale.
"""

from __future__ import annotations

import os
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

CACHE_DIR = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "rw-promptforge"
CACHE_FILE = CACHE_DIR / "embeddings.pkl"


class EmbeddingCache:
    """File-backed LRU cache keyed on (model, text) tuples.

    Stored as OrderedDict of key -> (tuple[float, ...], timestamp).
    Tuples instead of numpy arrays so the cache works without numpy installed
    (import numpy lazily in callers that need arrays).
    """

    def __init__(self, path: Path | None = None, maxsize: int = 10_000) -> None:
        self.path = path or CACHE_FILE
        self.maxsize = maxsize
        self._cache: OrderedDict[tuple[str, str], tuple[tuple[float, ...], float]] = (
            OrderedDict()
        )
        self.hits = 0
        self.misses = 0
        self._load()

    @staticmethod
    def _key(model: str, text: str) -> tuple[str, str]:
        return (model, text)

    def get(self, model: str, text: str) -> tuple[float, ...] | None:
        """Return cached embedding or None. Moves entry to most-recent."""
        key = self._key(model, text)
        entry = self._cache.get(key)
        if entry is None:
            self.misses += 1
            return None
        self._cache.move_to_end(key)
        self.hits += 1
        return entry[0]

    def set(self, model: str, text: str, embedding: Iterable[float]) -> None:
        """Store embedding, evicting LRU entry when at capacity."""
        key = self._key(model, text)
        self._cache[key] = (tuple(embedding), time.time())
        self._cache.move_to_end(key)
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)  # evict oldest

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def get_many(self, model: str, texts: list[str]) -> tuple[list[tuple[float, ...] | None], list[int]]:
        """Bulk lookup. Returns (results, missing_indices)."""
        results: list[tuple[float, ...] | None] = []
        missing: list[int] = []
        for i, text in enumerate(texts):
            entry = self.get(model, text)
            results.append(entry)
            if entry is None:
                missing.append(i)
        return results, missing

    def set_many(self, model: str, texts: list[str], embeddings: list[Iterable[float]]) -> None:
        for text, emb in zip(texts, embeddings):
            self.set(model, text, emb)

    # -- persistence -------------------------------------------------------

    def save(self) -> None:
        """Persist cache to disk (best-effort; failure is non-fatal)."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump(
                    {"version": 1, "maxsize": self.maxsize, "cache": self._cache}, f
                )
            os.replace(tmp, self.path)
        except (OSError, pickle.PickleError):
            # Cache save failure is non-fatal — embeddings can be recomputed.
            pass

    def _load(self) -> None:
        """Load cache from disk; corrupt/missing files start fresh."""
        try:
            with open(self.path, "rb") as f:
                payload = pickle.load(f)
            if payload.get("version") != 1:
                return
            cache = payload.get("cache")
            if isinstance(cache, dict):
                self._cache = OrderedDict(cache)
        except (OSError, pickle.PickleError, EOFError):
            self._cache = OrderedDict()


def clear_cache() -> None:
    """Remove on-disk cache file. Any open EmbeddingCache keeps its in-memory copy."""
    try:
        CACHE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
