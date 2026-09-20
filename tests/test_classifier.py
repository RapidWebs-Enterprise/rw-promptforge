"""Tests for rw_promptforge.classifier.FailureClassifier."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from dataclasses import dataclass

from rw_promptforge.classifier import FEATURES, LABELS, FailureClassifier
from rw_promptforge.clustering import ClusterLabel


@dataclass
class FakeTrace:
    what_happened: str = ""
    user_correction: str = ""
    agent_response: str = ""
    context: str = ""
    skill_name: str = ""
    severity: int = 0
    failure_type: str = "general"


def _traces(n: int, severity: int, text: str = "boom") -> list[FakeTrace]:
    return [FakeTrace(severity=severity, what_happened=text * (i + 1)) for i in range(n)]


def test_feature_vector_layout():
    t = FakeTrace(
        severity=3, what_happened="abc", user_correction="fix",
        skill_name="git", failure_type="general",
    )
    f = FailureClassifier.features(t)
    assert len(f) == len(FEATURES)
    assert f[0] == 3.0          # severity
    assert f[1] == 3.0          # len("abc")
    assert f[2] == 1.0          # has_correction
    assert f[3] == 0.0          # no response
    assert f[5] == 1.0          # skill known
    assert f[6] == 1.0          # general type


def test_predict_unfitted_returns_default():
    clf = FailureClassifier()
    label, conf = clf.predict(FakeTrace())
    assert label == ClusterLabel.NEW_PATTERN
    assert conf == 0.0


def test_fit_and_predict_separates_classes():
    # Two classes separated on multiple features, not just one
    systemic = [
        FakeTrace(severity=9, what_happened="system error " * 8,
                  user_correction="fix it", context="prod", skill_name="deploy")
        for _ in range(20)
    ]
    one_off = [
        FakeTrace(severity=0, what_happened="x", failure_type="typo")
        for _ in range(20)
    ]
    traces = systemic + one_off
    labels = [ClusterLabel.SYSTEMIC] * 20 + [ClusterLabel.ONE_OFF] * 20

    clf = FailureClassifier()
    clf.fit(traces, labels)
    assert clf.is_fitted

    label, conf = clf.predict(systemic[0])
    assert label == ClusterLabel.SYSTEMIC
    assert conf > 0.5

    label2, conf2 = clf.predict(one_off[0])
    assert label2 == ClusterLabel.ONE_OFF
    assert conf2 > 0.5


def test_save_and_load_roundtrip(tmp_path):
    clf = FailureClassifier()
    systemic = [
        FakeTrace(severity=8, what_happened="big error " * 6, skill_name="x")
        for _ in range(15)
    ]
    one_off = [FakeTrace(severity=0, what_happened="q") for _ in range(15)]
    clf.fit(systemic + one_off, [ClusterLabel.SYSTEMIC] * 15 + [ClusterLabel.ONE_OFF] * 15)

    path = tmp_path / "model.pkl"
    clf.save(path)
    assert path.exists()

    loaded = FailureClassifier.load(path)
    assert loaded.is_fitted
    label, conf = loaded.predict(systemic[0])
    assert label == ClusterLabel.SYSTEMIC
