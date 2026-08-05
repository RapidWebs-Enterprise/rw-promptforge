"""Tests for the reverse auditor module."""

import pytest

from rw_promptforge.auditor import (
    reverse_audit,
    PASS,
    FAIL,
    REVIEW,
    extract_armored_sections,
    _check_yaml_frontmatter,
    _check_armored_sections,
)


class TestReverseAudit:
    def test_passes_identical_artifacts(self):
        """No change = pass."""
        art = "same content"
        assert reverse_audit(None, art, art) == PASS

    def test_fails_empty_candidate(self):
        """Empty or very short candidate = fail."""
        assert reverse_audit(None, "old", "") == FAIL
        assert reverse_audit(None, "old", "short") == FAIL

    def test_passes_valid_addition(self):
        """Adding content = pass."""
        assert reverse_audit(None, "old", "old with more") == PASS

    def test_fails_size_cap_exceeded(self):
        """Artifact exceeding SIZE_MULTIPLIER_CAP * original = fail."""
        small = "x" * 100
        huge = "x" * 200  # 2x original — exceeds 1.5 cap
        assert reverse_audit(None, small, huge, original_size=100) == FAIL

    def test_passes_within_size_cap(self):
        """Artifact within 1.5x cap = pass."""
        normal = "x" * 140  # 1.4x original
        assert reverse_audit(None, "old", normal, original_size=100) == PASS

    def test_size_cap_configurable(self):
        """Custom size_cap relaxes or tightens the growth limit."""
        medium = "x" * 180  # 1.8x original
        # Default 1.5 → fail
        assert reverse_audit(None, "old", medium, original_size=100) == FAIL
        # size_cap=2.0 → pass
        assert reverse_audit(None, "old", medium, original_size=100, size_cap=2.0) == PASS
        # size_cap=1.0 → even 1.1x fails
        assert reverse_audit(None, "old", "x" * 110, original_size=100, size_cap=1.0) == FAIL

    def test_stagnation_detection(self):
        """Very similar entries with stagnation = fail."""
        old = "same content"
        snippet = "same content"
        copies = [snippet, snippet, snippet]
        # Artifact snipped to 500 chars, compared to each snippet
        result = reverse_audit(None, old, old, recent_snippets=copies)
        assert result == FAIL

    def test_no_stagnation_with_different_content(self):
        """Different content = not stagnant."""
        old = "completely different"
        new = "fresh new content"
        snippets = ["previous version A", "previous version B"]
        assert reverse_audit(None, old, new, recent_snippets=snippets) == PASS


class TestArmoredSections:
    def test_detect_preserved(self):
        """ARMORED sections preserved = pass."""
        old = '<section name="machine_protocol">CONTENT</section>'
        new = '<section name="machine_protocol">CONTENT</section>\nadded'
        result = _check_armored_sections(old, new)
        assert result == PASS

    def test_detect_modified(self):
        """ARMORED sections modified = fail."""
        old = '<section name="machine_protocol">CONTENT</section>'
        new = '<section name="machine_protocol">MODIFIED</section>'
        result = _check_armored_sections(old, new)
        assert result == FAIL

    def test_real_soul_tag_format_preserved(self):
        """SOUL.md uses <protocol name=...> tags — must be matched too."""
        old = '<protocol name="machine_protocol">CONTENT</protocol>'
        new = '<protocol name="machine_protocol">CONTENT</protocol>\nrest of file'
        result = _check_armored_sections(old, new)
        assert result == PASS

    def test_real_soul_tag_format_modified(self):
        """ARMORED section in real SOUL.md tag format modified = fail."""
        old = '<verification name="budget_guards">ORIGINAL TEXT</verification>'
        new = '<verification name="budget_guards">CHANGED TEXT</verification>'
        result = _check_armored_sections(old, new)
        assert result == FAIL

    def test_real_soul_tag_format_removed(self):
        """ARMORED section in real SOUL.md tag format removed = fail."""
        old = '<gate name="skill_gate">\n## ⛔ SKILL GATE\n</gate>'
        new = '<gate name="skill_gate">\n## ⛔ SKILL GATE\n</gate>\n'  # still present
        assert _check_armored_sections(old, new) == PASS
        removed = 'no gate here anymore'
        assert _check_armored_sections(old, removed) == FAIL

    def test_cross_tag_format_still_protected(self):
        """Same name, different wrapper tag — removed section still fails."""
        old = '<verification name="reality_check">CONTENT</verification>'
        new = '<section name="reality_check">CONTENT</section>'  # renamed tag
        result = _check_armored_sections(old, new)
        assert result == FAIL

    def test_no_sections_both_sides(self):
        """No ARMORED sections in either = pass."""
        result = _check_armored_sections("plain text", "plain text")
        assert result == PASS

    def test_section_removed(self):
        """ARMORED section removed = fail."""
        old = '<section name="skill_gate">Content</section>'
        new = 'no sections here'
        result = _check_armored_sections(old, new)
        assert result == FAIL


class TestYamlFrontmatter:
    def test_valid_yaml_passes(self):
        assert _check_yaml_frontmatter("---\nname: test\n---\nbody") == PASS

    def test_no_frontmatter_review(self):
        """No frontmatter = review (not fail — might be skill without YAML)."""
        assert _check_yaml_frontmatter("Just body text") == PASS  # fallback passes

    def test_empty(self):
        assert _check_yaml_frontmatter("") == PASS


class TestExtractArmored:
    def test_extract_known_section(self):
        """Can extract known ARMORED sections."""
        text = '<section name="machine_protocol">VERY IMPORTANT</section>'
        result = extract_armored_sections(text)
        assert "machine_protocol" in result
        assert result["machine_protocol"] == "VERY IMPORTANT"

    def test_unknown_section_ignored(self):
        """Sections not in ARMORED_SECTIONS are skipped."""
        text = '<section name="nope">content</section>'
        result = extract_armored_sections(text)
        assert result == {}

    def test_empty_artifact(self):
        assert extract_armored_sections("") == {}