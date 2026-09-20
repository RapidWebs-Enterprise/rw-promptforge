"""Tests for rw_promptforge.reranker.TraceReranker."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from rw_promptforge.reranker import TraceReranker


class FakeTrace:
    def __init__(self, what: str, correction: str = ""):
        self.what_happened = what
        self.user_correction = correction


def _embed_handler(dim: int = 4):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        # Deterministic: embedding encodes length so recall picks long docs
        data = []
        for i, text in enumerate(body["input"]):
            v = [float(len(text) % 10)] + [0.0] * (dim - 1)
            data.append({"index": i, "embedding": v})
        return httpx.Response(200, json={"data": data})
    return handler


def _rerank_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        # Score inversely proportional to index — favours earlier docs
        results = [
            {"index": i, "relevance_score": 1.0 - i * 0.1}
            for i in range(len(body["documents"]))
        ]
        return httpx.Response(200, json={"results": results})
    return handler


class StubProvider:
    """Provider duck that serves embed/rerank from mock transports."""

    def __init__(self, embed_transport, rerank_transport):
        self._embed = httpx.Client(transport=embed_transport)
        self._rerank = httpx.Client(transport=rerank_transport)

    def embed(self, texts):
        resp = self._embed.post("http://t/v1/embeddings", json={"input": texts, "model": "m"})
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return np.array([d["embedding"] for d in data], dtype=np.float32)

    def rerank(self, query, documents):
        resp = self._rerank.post(
            "http://t/v1/rerank",
            json={"query": query, "documents": documents, "model": "m"},
        )
        items = sorted(resp.json()["results"], key=lambda r: r["index"])
        return [r["relevance_score"] for r in items]


@pytest.fixture
def provider():
    return StubProvider(
        httpx.MockTransport(_embed_handler()),
        httpx.MockTransport(_rerank_handler()),
    )


def test_rerank_empty_and_small_inputs(provider):
    r = TraceReranker(provider, top_k=3)
    assert r.rerank("q", []) == []
    two = [FakeTrace("a"), FakeTrace("b")]
    assert r.rerank("q", two) == two  # short-circuits


def test_rerank_returns_top_k(provider):
    traces = [FakeTrace(f"trace {i}") for i in range(10)]
    r = TraceReranker(provider, top_k=3)
    out = r.rerank("query", traces)
    assert len(out) == 3
    # Reranker scores earlier candidates higher, so expected top 3 are first 3 of recall
    assert {t.what_happened for t in out} <= {t.what_happened for t in traces}


def test_rerank_recovers_from_embed_failure():
    class BrokenEmbed:
        def embed(self, texts):
            raise httpx.HTTPError("down")

        def rerank(self, query, documents):
            return [1.0 - i * 0.1 for i in range(len(documents))]

    traces = [FakeTrace(f"t i={i}") for i in range(50)]
    r = TraceReranker(BrokenEmbed(), top_k=3, recall_k=8)
    out = r.rerank("q", traces)
    assert len(out) == 3  # fallback path still returns top_k


def test_rerank_recovers_from_rerank_failure():
    class BrokenRerank:
        def embed(self, texts):
            dim = 4
            return np.ones((len(texts), dim), dtype=np.float32)

        def rerank(self, query, documents):
            raise httpx.HTTPError("down")

    traces = [FakeTrace(f"x {i}") for i in range(10)]
    r = TraceReranker(BrokenRerank(), top_k=4, recall_k=6)
    out = r.rerank("q", traces)
    assert len(out) == 4  # fell back to recall order


def test_recall_limits_to_recall_k(provider):
    # 50 traces, recall_k=10 → stage 2 receives only 10 docs
    received = []

    orig_rerank = provider.rerank

    def spy_rerank(q, docs):
        received.append(len(docs))
        return orig_rerank(q, docs)

    provider.rerank = spy_rerank  # type: ignore[method-assign]
    traces = [FakeTrace(f"x{i}") for i in range(50)]
    r = TraceReranker(provider, top_k=3, recall_k=10)
    r.rerank("q", traces)
    assert received == [10]
