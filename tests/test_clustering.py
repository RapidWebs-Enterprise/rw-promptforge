"""Tests for rw_promptforge.clustering.TraceClusterer."""

from __future__ import annotations

import numpy as np
import pytest

_hdbscan = pytest.importorskip("hdbscan")  # noqa: F841 — skip if [ml] missing

from rw_promptforge.clustering import ClusterLabel, TraceClusterer


def _emb(seed: int, n: int, dim: int = 8) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random((n, dim)).astype(np.float64)


def test_insufficient_traces_all_noise():
    tc = TraceClusterer(min_cluster_size=3)
    labels, clusters = tc.cluster(_emb(0, 2))
    assert (labels == -1).all()
    assert clusters == {}


def test_single_trace_noise():
    tc = TraceClusterer(min_cluster_size=3)
    labels, _ = tc.cluster(_emb(0, 1))
    assert labels.tolist() == [-1]


def test_two_distinct_clusters():
    # Two tight blobs far apart → should form 2 clusters, no noise
    a = _emb(1, 6) * 0.01                      # blob near origin
    b = _emb(2, 6) * 0.01 + 10.0               # blob far away
    X = np.vstack([a, b])
    tc = TraceClusterer(min_cluster_size=3, systemic_min_size=5, heavy_threshold=5.0)
    labels, _ = tc.cluster(X)
    non_noise = [l for l in labels if l != -1]
    assert len(set(non_noise)) == 2


def test_label_assignment_systemic():
    tc = TraceClusterer(min_cluster_size=2, systemic_min_size=5, heavy_threshold=5.0)
    labels = np.array([0, 0, 0, 0, 0, 1, 1])
    scores = [9.0, 8.0, 9.0, 8.0, 9.0, 1.0, 1.0]
    out = tc.label_clusters(labels, scores)
    assert out[0] == ClusterLabel.SYSTEMIC   # size 5, mean score 8.6
    assert out[1] == ClusterLabel.NEW_PATTERN  # size 2, below systemic_min_size


def test_label_assignment_recurring():
    tc = TraceClusterer(systemic_min_size=3, heavy_threshold=5.0)
    labels = np.array([0, 0, 0])
    out = tc.label_clusters(labels, [1.0, 2.0, 1.0])
    assert out[0] == ClusterLabel.RECURRING  # big enough, low severity


def test_label_for_noise():
    tc = TraceClusterer()
    assert tc.label_for_trace(-1, {}) == ClusterLabel.ONE_OFF
    assert tc.label_for_trace(3, {}) == ClusterLabel.NEW_PATTERN
    assert tc.label_for_trace(3, {3: ClusterLabel.SYSTEMIC}) == ClusterLabel.SYSTEMIC
