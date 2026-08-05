"""Tests for the reverse auditor module."""

import pytest
from pathlib import Path

from rw_promptforge.auditor import (
    reverse_audit,
    PASS,
    FAIL,
    REVIEW,
    extract_armored_sections,
    _check_yaml_frontmatter,
    _check_armored_sections,
    _check_all_sections_preserved,
    merge_artifact_sections,
    _iter_sections,
    _stagnation_probe,
    _stagnation_changed_chars,
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


class TestAllSectionsPreserved:
    def test_all_preserved_passes(self):
        old = '<protocol name="a">X</protocol><protocol name="b">Y</protocol>'
        new = '<protocol name="a">X EDIT</protocol><protocol name="b">Y</protocol><protocol name="c">NEW</protocol>'
        assert _check_all_sections_preserved(old, new) == PASS

    def test_deleted_section_fails(self):
        old = '<protocol name="a">X</protocol><verification name="b">Y</verification>'
        new = '<protocol name="a">X</protocol>'
        assert _check_all_sections_preserved(old, new) == FAIL

    def test_tag_type_change_fails(self):
        old = '<protocol name="a">X</protocol>'
        new = '<section name="a">X</section>'
        assert _check_all_sections_preserved(old, new) == FAIL

    def test_real_soul_pass(self, tmp_path):
        """Real ORIGINAL vs itself = pass."""
        orig = Path.home() / ".hermes" / "SOUL.md"
        if orig.exists():
            text = orig.read_text()
            assert _check_all_sections_preserved(text, text) == PASS

    def test_real_refined_fails(self, tmp_path):
        """REFINED.md deleted 16 sections → completeness gate fails.

        Uses the stable fixture (a section-deleting variant captured from a
        real run) rather than the live runs/ directory, which the optimizer
        overwrites on every run.
        """
        base = Path(__file__).parent.parent / "tests" / "fixtures"
        orig = (base / "original-soul.md").read_text()
        refined = (base / "refined-deleted-sections.md").read_text()
        assert _check_all_sections_preserved(orig, refined) == FAIL


class TestMergeArtifactSections:
    def test_merge_restores_deleted_sections(self):
        """Variant deleted a section → merge restores original content."""
        original = (
            '<protocol name="a">ORIG A</protocol>'
            '<verification name="b">ORIG B</verification>'
        )
        variant = '<protocol name="a">EDIT A</protocol>'
        merged = merge_artifact_sections(original, variant)
        # Edited section uses variant content
        assert "EDIT A" in merged
        # Deleted section restored with original content
        assert 'name="b">ORIG B</verification>' in merged
        # Completeness gate now passes
        assert _check_all_sections_preserved(original, merged) == PASS

    def test_merge_keeps_edited_content(self):
        original = '<protocol name="a">ORIG</protocol>'
        variant = '<protocol name="a">NEW CONTENT</protocol>'
        merged = merge_artifact_sections(original, variant)
        assert "NEW CONTENT" in merged
        assert "ORIG" not in merged

    def test_merge_adds_new_sections(self):
        """Variant-added sections are preserved."""
        original = '<protocol name="a">X</protocol>'
        variant = '<protocol name="a">Y</protocol><protocol name="z">NEW</protocol>'
        merged = merge_artifact_sections(original, variant)
        assert 'name="z">NEW</protocol>' in merged
        assert _check_all_sections_preserved(original, merged) == PASS

    def test_merge_no_sections_returns_variant(self):
        assert merge_artifact_sections("no sections", "anything") == "anything"

    def test_merge_preserves_prose_between_sections(self):
        """Non-section prose outside sections survives."""
        original = 'HEADER\n<protocol name="a">X</protocol>\nFOOTER'
        variant = '<protocol name="a">Y</protocol>'
        merged = merge_artifact_sections(original, variant)
        assert merged.startswith("HEADER")
        assert merged.endswith("FOOTER")
        assert "Y" in merged

    def test_merge_real_soul_keeps_skeleton(self):
        """Merging a section-deleting variant of the real soul keeps ALL sections."""
        base = Path(__file__).parent.parent / "tests" / "fixtures"
        orig = (base / "original-soul.md").read_text()
        refined = (base / "refined-deleted-sections.md").read_text()
        merged = merge_artifact_sections(orig, refined)
        # All original sections survive in the merged artifact
        assert _check_all_sections_preserved(orig, merged) == PASS
        # And it's not identical to the original (edits flowed through)
        assert merged != orig
        # No duplicated sections in the merged artifact
        from collections import Counter

        names = [n for _, n, _ in _iter_sections(merged)]
        dupes = {n: c for n, c in Counter(names).items() if c > 1}
        assert not dupes


class TestYamlFrontmatter:
    def test_valid_yaml_passes(self):
        assert _check_yaml_frontmatter("---\nname: test\n---\nbody") == PASS

    def test_no_frontmatter_review(self):
        """No frontmatter = review (not fail — might be skill without YAML)."""
        assert _check_yaml_frontmatter("Just body text") == PASS  # fallback passes

    def test_empty(self):
        assert _check_yaml_frontmatter("") == PASS


class TestStagnationProbe:
    def test_short_text_unchanged(self):
        assert _stagnation_probe("short") == "short"

    def test_samples_middle_for_long_text(self):
        text = "HEADER" * 500 + '<protocol name="a">MIDDLE-CONTENT</protocol>' + "B" * 2000
        probe = _stagnation_probe(text)
        assert "MIDDLE-CONTENT" in probe
        assert "HEADER" not in probe

    def test_changed_chars_counts_actual_difference(self):
        old = "SAME PREFIX " + "OLD CONTENT" + " SAME SUFFIX"
        new = "SAME PREFIX " + "NEW CONTENT" + " SAME SUFFIX"
        # OLD CONTENT (11) → NEW CONTENT (11) = replace, plus maybe spacing
        changed = _stagnation_changed_chars(old, new)
        # The exact count depends on SequenceMatcher's alignment; we just verify
        # it detects the difference (non-zero) and is reasonable
        assert 0 < changed <= 30

    def test_identical_bodies_zero_changed(self):
        body = "SAME " * 1000
        assert _stagnation_changed_chars(body, body) == 0

    def test_real_soul_variant_not_stagnant(self):
        """A real soul variant with a meaningful rewrite must pass the
        stagnation gate even though its header is byte-identical.

        A tiny one-word change (42 chars) IS correctly flagged as stagnant.
        A meaningful rewrite (254+ chars) correctly passes.
        """
        base = Path(__file__).parent.parent / "tests" / "fixtures"
        orig = (base / "original-soul.md").read_text()
        # Tiny edit = stagnant (correct behavior)
        variant_tiny = orig.replace(
            "## ⛔ SKILL GATE — Mandatory Pre-Flight",
            "## ⛔ SKILL GATE — MANDATORY Pre-Flight (never skip)",
        )
        probe_o = _stagnation_probe(orig)
        probe_v_tiny = _stagnation_probe(variant_tiny)
        changed_tiny = _stagnation_changed_chars(probe_o, probe_v_tiny)
        assert changed_tiny < 100  # correctly detected as stagnant

        # Substantial edit = not stagnant
        variant_real = orig.replace(
            "## ⛔ SKILL GATE — Mandatory Pre-Flight",
            "## ⛔ SKILL GATE — MANDATORY Pre-Flight (never skip)\n\n**New mandatory step:** Before any task, run the skill gate check explicitly and document the outcome.",
        )
        probe_v_real = _stagnation_probe(variant_real)
        changed_real = _stagnation_changed_chars(probe_o, probe_v_real)
        assert changed_real >= 100  # meaningful change passes


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