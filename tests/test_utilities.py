"""Tests for utility functions (truncate, similarity)."""

from rw_promptforge.datastore.models import (
    truncate_artifact,
    jaccard_similarity,
    sequence_similarity,
    compute_artifact_meta,
    compute_multipliers,
    CategoryScores,
)


class TestTruncate:
    def test_under_limit_unchanged(self):
        assert truncate_artifact("hello", max_chars=100) == "hello"

    def test_over_limit_truncated(self):
        t = truncate_artifact("x" * 200, max_chars=20)
        assert "... [TRUNCATED] ..." in t
        assert len(t) < 50

    def test_exact_boundary(self):
        s = "x" * 20
        assert truncate_artifact(s, max_chars=20) == s


class TestJaccard:
    def test_same(self):
        assert jaccard_similarity("a b c", "a b c") == 1.0

    def test_disjoint(self):
        assert jaccard_similarity("a b c", "d e f") < 0.01

    def test_partial(self):
        s = jaccard_similarity("a b c d", "a b e f")
        assert 0.33 < s < 0.5

    def test_empty(self):
        assert jaccard_similarity("", "") == 0.0

    def test_one_empty(self):
        assert jaccard_similarity("a b c", "") == 0.0


class TestSequenceSimilarity:
    def test_same(self):
        assert sequence_similarity("same", "same") == 1.0

    def test_different(self):
        assert sequence_similarity("abc", "xyz") < 0.5

    def test_variable_length(self):
        """Works on strings of different lengths."""
        s = sequence_similarity("short", "much longer text here")
        assert 0 < s < 1.0


class TestArtifactMeta:
    def test_computes_meta(self):
        meta = compute_artifact_meta("test", "soul", "line1\nline2\n", region_count=3)
        assert meta["name"] == "test"
        assert meta["type"] == "soul"
        assert meta["total_lines"] == 2
        assert meta["region_count"] == 3
        assert meta["total_chars"] == 12
        assert meta["size_mb"] > 0

    def test_empty_artifact(self):
        meta = compute_artifact_meta("empty", "skill", "")
        assert meta["total_lines"] == 0
        assert meta["total_chars"] == 0


class TestComputeMultipliers:
    def test_improvement_positive(self):
        b = CategoryScores(0.5, 0.5, 0.5, 0.5)
        a = CategoryScores(0.6, 0.6, 0.6, 0.6)
        m = compute_multipliers(b, a)
        for v in m.multipliers.values():
            assert abs(v - 0.2) < 0.01

    def test_regression_negative(self):
        b = CategoryScores(0.6, 0.6, 0.6, 0.6)
        a = CategoryScores(0.5, 0.5, 0.5, 0.5)
        m = compute_multipliers(b, a)
        for v in m.multipliers.values():
            assert abs(v + 0.1667) < 0.01

    def test_zero_prev_no_crash(self):
        b = CategoryScores(0.0, 0.0, 0.0, 0.0)
        a = CategoryScores(0.1, 0.1, 0.1, 0.1)
        m = compute_multipliers(b, a)
        for v in m.multipliers.values():
            assert isinstance(v, float)

    def test_capped_extreme(self):
        """Extreme multipliers are capped at ±5.0."""
        b = CategoryScores(0.01, 0.01, 0.01, 0.01)
        a = CategoryScores(0.99, 0.99, 0.99, 0.99)
        m = compute_multipliers(b, a)
        for v in m.multipliers.values():
            assert abs(v) <= 5.0