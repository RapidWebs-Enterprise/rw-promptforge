"""Tests for Provider.embed() and Provider.rerank() — ML enhancement methods.

All HTTP calls are mocked with httpx MockTransport; no network access.
"""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from rw_promptforge.cache import EmbeddingCache
from rw_promptforge.provider import Provider


def _embed_handler(dim: int = 4):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        data = [
            {"index": i, "embedding": [0.1 * (i + 1)] * dim}
            for i in range(len(body["input"]))
        ]
        return httpx.Response(200, json={"data": data})

    return handler


def _rerank_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        results = [
            {"index": i, "relevance_score": 1.0 / (i + 1)}
            for i in range(len(body["documents"]))
        ]
        return httpx.Response(200, json={"results": results})

    return handler


class CountingTransport(httpx.MockTransport):
    """MockTransport that counts handle_request calls."""

    def __init__(self, handler):
        super().__init__(handler)
        self.count = 0

    def handle_request(self, request):
        self.count += 1
        return super().handle_request(request)


def make_provider(transport, **kwargs) -> Provider:
    p = Provider(endpoint="http://test/v1", api_key="k", model="m", **kwargs)
    p._client = httpx.Client(transport=transport)
    return p


def test_embed_calls_endpoint_and_parses():
    transport = CountingTransport(_embed_handler())
    p = make_provider(transport)
    out = p.embed(["alpha", "beta"])
    assert isinstance(out, np.ndarray)
    assert out.shape == (2, 4)
    assert out[0][0] == pytest.approx(0.1)
    assert out[1][0] == pytest.approx(0.2)
    assert transport.count == 1


def test_embed_empty_input():
    p = make_provider(CountingTransport(_embed_handler()))
    out = p.embed([])
    assert out.shape == (0, 0)


def test_embed_uses_cache_on_second_call(tmp_path):
    cache = EmbeddingCache(path=tmp_path / "emb.pkl", maxsize=100)
    transport = CountingTransport(_embed_handler())
    p = make_provider(transport, cache=cache)

    first = p.embed(["hello", "world"])
    assert transport.count == 1

    second = p.embed(["hello", "world"])
    assert transport.count == 1  # served from cache
    assert np.allclose(first, second)


def test_embed_mixed_cache_hits(tmp_path):
    cache = EmbeddingCache(path=tmp_path / "emb.pkl", maxsize=100)
    p = make_provider(CountingTransport(_embed_handler()), cache=cache)
    p.embed(["a", "b"])  # populate cache

    transport = CountingTransport(_embed_handler())
    p._client = httpx.Client(transport=transport)
    out = p.embed(["a", "c"])
    assert transport.count == 1  # one HTTP call for the miss only
    assert out.shape == (2, 4)
    # "a" came from cache (value 0.1), "c" is fresh index 0 → 0.1 too
    assert np.allclose(out[0], out[1]) or out[0][0] == pytest.approx(0.1)


def test_rerank_returns_scores():
    p = make_provider(CountingTransport(_rerank_handler()))
    scores = p.rerank("query", ["d0", "d1", "d2"])
    assert len(scores) == 3
    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(0.5)
    assert scores[2] == pytest.approx(1.0 / 3.0)


def test_rerank_empty():
    p = make_provider(CountingTransport(_rerank_handler()))
    assert p.rerank("q", []) == []


def test_embed_http_error_propagates():
    transport = httpx.MockTransport(lambda r: httpx.Response(503))
    p = make_provider(transport)
    with pytest.raises(httpx.HTTPStatusError):
        p.embed(["x"])


def test_semantic_similarity_math():
    from rw_promptforge.datastore.models import semantic_similarity

    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]
    assert semantic_similarity(a, b) == pytest.approx(1.0)
    assert semantic_similarity(a, c) == pytest.approx(0.0)
    assert semantic_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero norm
    with pytest.raises(ValueError):
        semantic_similarity([1.0, 2.0], [1.0])
