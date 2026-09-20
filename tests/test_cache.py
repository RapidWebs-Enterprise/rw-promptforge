"""Tests for rw_promptforge.cache.EmbeddingCache."""

from __future__ import annotations

import pytest

from rw_promptforge.cache import EmbeddingCache


@pytest.fixture
def cache(tmp_path):
    return EmbeddingCache(path=tmp_path / "emb.pkl", maxsize=3)


def test_get_missing_returns_none(cache):
    assert cache.get("model", "text") is None
    assert cache.misses == 1


def test_set_and_get_roundtrip(cache):
    cache.set("m", "t", [1.0, 2.0, 3.0])
    got = cache.get("m", "t")
    assert got == (1.0, 2.0, 3.0)
    assert cache.hits == 1


def test_keyed_on_model_and_text(cache):
    cache.set("model-a", "same text", [0.1])
    cache.set("model-b", "same text", [0.9])
    assert cache.get("model-a", "same text") == (0.1,)
    assert cache.get("model-b", "same text") == (0.9,)


def test_lru_eviction(cache):
    cache.set("m", "a", [1.0])
    cache.set("m", "b", [2.0])
    cache.set("m", "c", [3.0])
    assert len(cache) == 3  # at capacity
    cache.get("m", "a")  # refresh "a"
    cache.set("m", "d", [4.0])  # should evict "b" (oldest untouched)
    assert cache.get("m", "a") is not None
    assert cache.get("m", "b") is None
    assert cache.get("m", "c") is not None
    assert cache.get("m", "d") is not None


def test_get_many_reports_missing_indices(cache):
    cache.set("m", "x", [0.5])
    results, missing = cache.get_many("m", ["x", "y", "z"])
    assert results[0] == (0.5,)
    assert results[1] is None and results[2] is None
    assert missing == [1, 2]


def test_save_and_reload(tmp_path):
    path = tmp_path / "persist.pkl"
    c1 = EmbeddingCache(path=path, maxsize=10)
    c1.set("m", "text", [7.0, 8.0])
    c1.save()

    c2 = EmbeddingCache(path=path, maxsize=10)
    assert c2.get("m", "text") == (7.0, 8.0)


def test_corrupt_file_starts_fresh(tmp_path):
    path = tmp_path / "corrupt.pkl"
    path.write_bytes(b"not a pickle")
    c = EmbeddingCache(path=path)
    assert len(c) == 0
    assert c.get("m", "t") is None
