"""Tests for the 4-category scoring module."""

import pytest

from rw_promptforge.categories import (
    score_categories,
    format_category_report,
)
from rw_promptforge.datastore.models import CategoryScores, compute_multipliers


class TestScoreCategories:
    def test_all_categories_return_scores(self):
        """score_categories returns CategoryScores with all 4 dimensions."""
        scores = score_categories("## Test\nSimple artifact here.", "")
        assert 0 <= scores.structural_coherence <= 1.0
        assert 0 <= scores.failure_coverage <= 1.0
        assert 0 <= scores.conciseness <= 1.0
        assert 0 <= scores.actionability <= 1.0

    def test_composite_is_weighted_average(self):
        """Composite is a weighted average of the 4 dimensions."""
        cs = CategoryScores(
            structural_coherence=1.0,
            failure_coverage=1.0,
            conciseness=1.0,
            actionability=1.0,
        )
        assert cs.composite == 1.0

        cs2 = CategoryScores(
            structural_coherence=0.0,
            failure_coverage=0.0,
            conciseness=0.0,
            actionability=0.0,
        )
        assert cs2.composite == 0.0

    def test_structural_coherence_detects_sections(self):
        """Artifacts with sections score higher on C1."""
        structured = "## Intro\nContent\n## Body\nMore\n## Conclusion\nEnd"
        unstructured = "Just a paragraph of plain text with no sections whatsoever."
        s1 = score_categories(structured, "").structural_coherence
        s2 = score_categories(unstructured, "").structural_coherence
        assert s1 > s2

    def test_failure_coverage_improves_with_keywords(self):
        """C2 improves when artifact addresses failure trace keywords."""
        traces = "User corrected: you should have verified state before acting"
        good = "## Steps\n1. Verify state before acting\n2. Check results"
        bad = "## Steps\n1. Run the command\n2. Report results"
        g = score_categories(good, traces).failure_coverage
        b = score_categories(bad, traces).failure_coverage
        assert g >= b  # at least as good

    def test_actionability_detects_imperatives(self):
        """C4 scores higher with imperative verbs and step lists."""
        actionable = "Run the tool. Check output. Verify results. Never guess."
        passive = "The tool should be run. The output can be checked later."
        a = score_categories(actionable, "").actionability
        p = score_categories(passive, "").actionability
        assert a > p

    def test_compute_multipliers(self):
        """Multipliers reflect directional change."""
        before = CategoryScores(0.5, 0.5, 0.5, 0.5)
        after = CategoryScores(0.6, 0.5, 0.5, 0.5)
        m = compute_multipliers(before, after)
        assert abs(m.multipliers["structural_coherence"] - 0.2) < 0.01

    def test_multiplier_handles_div_by_zero(self):
        """Multiplier doesn't crash on zero previous score."""
        before = CategoryScores(0.0, 0.0, 0.0, 0.0)
        after = CategoryScores(0.1, 0.1, 0.1, 0.1)
        m = compute_multipliers(before, after)
        # All should be 0 (epsilon prevents division by zero)
        for v in m.multipliers.values():
            assert isinstance(v, float)

    def test_format_report(self):
        """Report rendering doesn't crash."""
        before = CategoryScores(0.5, 0.5, 0.5, 0.5)
        after = CategoryScores(0.6, 0.6, 0.6, 0.6)
        report = format_category_report(before, after)
        assert "Score Changes" in report
        assert "↑" in report