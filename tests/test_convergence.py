"""Tests for convergence detection (with reverse audit fixes)."""

import pytest

from rw_promptforge.convergence import (
    convergence_score,
    is_converged,
    check_redundancy,
    check_semantic_stability,
    check_gain_saturation,
    format_convergence_report,
)
from rw_promptforge.datastore.models import (
    LearningLogEntry,
    CategoryScores,
    MultiplierEntry,
    jaccard_similarity,
    sequence_similarity,
)


class TestSimilarityUtilities:
    def test_jaccard_same(self):
        assert jaccard_similarity("hello world", "hello world") == 1.0

    def test_jaccard_different(self):
        assert jaccard_similarity("abc def", "ghi jkl") < 0.1

    def test_jaccard_partial(self):
            s = jaccard_similarity("a b c d", "a b e f")
            assert 0.33 <= s <= 0.5

    def test_jaccard_empty(self):
        assert jaccard_similarity("", "") == 0.0

    def test_sequence_same(self):
        assert sequence_similarity("hello", "hello") == 1.0

    def test_sequence_different(self):
        assert sequence_similarity("abc", "xyz") < 0.1

    def test_sequence_partial(self):
        s = sequence_similarity("hello world", "hello there")
        assert 0.5 < s < 0.8

    def test_sequence_variable_length(self):
        """SequenceMatcher works on different-length strings."""
        s = sequence_similarity("short", "much longer text")
        assert 0 < s < 1.0  # no crash, valid result


class TestConvergenceScore:
    def test_returns_zero_with_insufficient_history(self):
        assert convergence_score([]) == 0.0
        assert convergence_score([LearningLogEntry("r1", "neutral")]) == 0.0

    def test_improving_score_is_not_converged(self):
        """Active improvements should yield low convergence score."""
        entries = [
            LearningLogEntry("r1", "improvement", severity_after=2, artifact_snippet="aaa bbb ccc ddd eee"),
            LearningLogEntry("r2", "improvement", severity_after=1, artifact_snippet="aaa bbb ccc ddd"),
        ]
        score = convergence_score(entries)
        assert score < 0.5  # still improving

    def test_stable_score_is_converged(self):
        """Stable non-improving entries should yield high convergence score."""
        entries = [
            LearningLogEntry("r1", "improvement", severity_after=1, artifact_snippet="aaa bbb"),
            LearningLogEntry("r2", "neutral", severity_after=1, artifact_snippet="aaa ccc"),
            LearningLogEntry("r3", "neutral", severity_after=1, artifact_snippet="aaa ddd"),
        ]
        score = convergence_score(entries)
        assert score >= 0.3  # severity+size stability

    def test_fix_rate_low_is_converged(self):
        """Low fix rate = convergence signal (nothing left to fix)."""
        entries = [
            LearningLogEntry("r1", "neutral", severity_after=1, artifact_snippet="a"),
            LearningLogEntry("r2", "neutral", severity_after=1, artifact_snippet="b"),
            LearningLogEntry("r3", "neutral", severity_after=1, artifact_snippet="c"),
        ]
        score = convergence_score(entries)
        # All 3 signals: severity stable (0.4) + size stable (0.3) + low fix rate (0.3)
        assert score >= 0.7

    def test_score_bounded(self):
        """Convergence score never exceeds 1.0."""
        entries = [LearningLogEntry(f"r{i}", "neutral", artifact_snippet="x") for i in range(3)]
        assert convergence_score(entries) <= 1.0


class TestIsConverged:
    def test_not_converged_with_no_history(self):
        assert not is_converged([])

    def test_not_converged_with_improving_history(self):
        entries = [
            LearningLogEntry("r1", "improvement", severity_after=2),
            LearningLogEntry("r2", "improvement", severity_after=1),
        ]
        assert not is_converged(entries)

    def test_converged_with_stable_history(self):
        entries = [
            LearningLogEntry("r1", "neutral", severity_after=1, artifact_snippet="a"),
            LearningLogEntry("r2", "neutral", severity_after=1, artifact_snippet="b"),
            LearningLogEntry("r3", "neutral", severity_after=1, artifact_snippet="c"),
        ]
        assert is_converged(entries)

    def test_not_converged_with_all_zero_severity(self):
        """All zero severity with stable output = converged (nothing to fix)."""
        entries = [
            LearningLogEntry("r1", "neutral", severity_after=0, artifact_snippet="a"),
            LearningLogEntry("r2", "neutral", severity_after=0, artifact_snippet="b"),
            LearningLogEntry("r3", "neutral", severity_after=0, artifact_snippet="c"),
        ]
        # Score 0.7, 2 signals (>=0.6 + all neutral) → converged
        assert is_converged(entries)

    def test_new_artifact_not_converged(self):
        """Brand new artifact with no data yet should not converge."""
        assert not is_converged([])
        assert not is_converged([LearningLogEntry("r1", "improvement")])

    def test_threshold_configurable(self):
        """Lower threshold = converges sooner (tuning knob)."""
        # 2 improvements + 1 neutral: severity 0.4 + size 0.3 = 0.7,
        # fix_rate 2/3 → no fix signal; soft stop needs 2+ non-improvements (only 1)
        entries = [
            LearningLogEntry("r1", "improvement", severity_after=1, artifact_snippet="a" * 50),
            LearningLogEntry("r2", "improvement", severity_after=1, artifact_snippet="a" * 51),
            LearningLogEntry("r3", "neutral", severity_after=1, artifact_snippet="a" * 52),
        ]
        assert is_converged(entries, threshold=0.7)
        # Very strict threshold: not converged at 0.95
        assert not is_converged(entries, threshold=0.95)


class TestCheckRedundancy:
    def test_not_redundant_with_few_entries(self):
        assert not check_redundancy([])
        assert not check_redundancy([LearningLogEntry("r1", "neutral")])

    def test_redundant_with_similar_entries(self):
        entries = [
            LearningLogEntry(f"r{i}", "neutral", artifact_snippet="same text here") for i in range(5)
        ]
        assert check_redundancy(entries)

    def test_not_redundant_with_changing_entries(self):
        """Very different entries = not redundant."""
        entries = [
            LearningLogEntry("r1", "improvement", artifact_snippet="totally different first version"),
            LearningLogEntry("r2", "improvement", artifact_snippet="completely rewritten second version"),
            LearningLogEntry("r3", "improvement", artifact_snippet="major overhaul third version"),
        ]
        assert not check_redundancy(entries)


class TestSemanticStability:
    def test_same_text_is_stable(self):
        assert check_semantic_stability("hello world", "hello world", 0.95)

    def test_different_text_is_not_stable(self):
        assert not check_semantic_stability("hello world", "completely different", 0.95)

    def test_partial_change_threshold(self):
        """Small changes below threshold count as stable."""
        assert check_semantic_stability("hello world foo", "hello world bar", 0.5)


class TestGainSaturation:
    def test_no_prev_gain_saturated(self):
        assert not check_gain_saturation(None, CategoryScores())

    def test_small_gain_is_saturated(self):
        prev = CategoryScores(0.9, 0.9, 0.9, 0.9)
        curr = CategoryScores(0.9, 0.9, 0.9, 0.91)
        assert check_gain_saturation(prev, curr, threshold=0.2)

    def test_large_gain_is_not_saturated(self):
        prev = CategoryScores(0.5, 0.5, 0.5, 0.5)
        curr = CategoryScores(0.9, 0.9, 0.9, 0.9)
        assert not check_gain_saturation(prev, curr, threshold=0.02)


class TestFormatReport:
    def test_report_renders(self):
        entries = [LearningLogEntry("r1", "neutral")]
        report = format_convergence_report(entries)
        assert "Convergence Score" in report