"""Tests for the v2.1 frontier structures (Candidate / Frontier)."""

import pytest

from rw_promptforge.datastore.models import (
    Candidate,
    Frontier,
    CategoryScores,
    MetricType,
    OptimizeResult,
)


def make_candidate(composite: float, metric: float = 0.0, text: str = "") -> Candidate:
    scores = CategoryScores(
        structural_coherence=composite,
        failure_coverage=composite,
        conciseness=composite,
        actionability=composite,
    )
    return Candidate(
        artifact=text or f"artifact-{composite}",
        scores=scores,
        metric_score=metric,
        size_delta=1.0,
        round_generated=1,
    )


class TestCandidate:
    def test_rank_score_default(self):
        c = make_candidate(0.5)
        # 0.7 * 0.5 + 0.3 * 0.0
        assert c.rank_score == pytest.approx(0.35)

    def test_rank_score_with_metric(self):
        c = make_candidate(0.5, metric=1.0)
        # 0.7 * 0.5 + 0.3 * 1.0
        assert c.rank_score == pytest.approx(0.65)

    def test_metric_boost_can_win(self):
        strong_metric = make_candidate(0.4, metric=1.0)  # rank 0.58
        strong_composite = make_candidate(0.9, metric=0.0)  # rank 0.63
        assert strong_composite.rank_score > strong_metric.rank_score


class TestFrontier:
    def test_empty(self):
        f = Frontier()
        assert f.best is None
        assert f.spread == 0.0

    def test_add_sorts_descending(self):
        f = Frontier(max_size=3)
        f.add(make_candidate(0.3))
        f.add(make_candidate(0.9))
        f.add(make_candidate(0.6))
        assert [c.scores.composite for c in f.candidates] == pytest.approx([0.9, 0.6, 0.3])

    def test_max_size_evicts_worst(self):
        f = Frontier(max_size=2)
        f.add(make_candidate(0.3))
        f.add(make_candidate(0.9))
        f.add(make_candidate(0.6))
        assert len(f.candidates) == 2
        assert f.candidates[0].scores.composite == pytest.approx(0.9)
        assert f.candidates[1].scores.composite == pytest.approx(0.6)

    def test_best(self):
        f = Frontier(max_size=3)
        f.add(make_candidate(0.3))
        f.add(make_candidate(0.9))
        assert f.best.scores.composite == pytest.approx(0.9)

    def test_spread(self):
        f = Frontier(max_size=3)
        f.add(make_candidate(0.9))
        f.add(make_candidate(0.4))
        assert f.spread == pytest.approx(0.7 * 0.5)  # rank-score difference

    def test_spread_single(self):
        f = Frontier()
        f.add(make_candidate(0.5))
        assert f.spread == 0.0


class TestMetricType:
    def test_values(self):
        assert MetricType.EXACT_MATCH == "exact_match"
        assert MetricType.ROUGE_L == "rouge_l"
        assert MetricType.ROUGE_2 == "rouge_2"
        assert MetricType.BLEU == "bleu"
        assert MetricType.TOOL_CALL_VALID == "tool_call_valid"
        assert MetricType.LLM == "llm"

    def test_from_string(self):
        assert MetricType("bleu") is MetricType.BLEU


class TestOptimizeResultFrontier:
    def test_defaults(self):
        r = OptimizeResult(
            artifact="a",
            rounds=0,
            failures_found=0,
            converged=False,
            failure_summary="",
            learning_log=[],
        )
        assert r.frontier == []
        assert r.metric_type == "llm"
        assert r.metric_score == 0.0

    def test_populated(self):
        c = make_candidate(0.7)
        r = OptimizeResult(
            artifact=c.artifact,
            rounds=1,
            failures_found=1,
            converged=True,
            failure_summary="ok",
            learning_log=[],
            frontier=[c],
            metric_type="rouge_l",
            metric_score=0.4,
        )
        assert r.frontier[0] is c
        assert r.metric_type == "rouge_l"
        assert r.metric_score == 0.4
