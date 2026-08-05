"""Tests for the LLM judge metric and chunked section-level reflection."""

import pytest

from rw_promptforge.reflector.engine import Reflector
from rw_promptforge.auditor import _replace_section_content


class JudgeStubProvider:
    """Provider with scripted judge/reflect responses."""

    def __init__(self, judge_score="0.85"):
        self.judge_score = judge_score
        self.calls = []

    def reflect(self, prompt: str, system: str | None = None) -> str:
        self.calls.append({"prompt": prompt[:80], "system": system})
        if system and "evaluator" in system:
            return self.judge_score
        # Section refinement: echo back an improved section
        return "IMPROVED SECTION CONTENT with explicit fix"

    def close(self):
        pass


@pytest.fixture
def judge_provider():
    return JudgeStubProvider()


@pytest.fixture
def reflector(judge_provider):
    return Reflector(judge_provider)


class TestLLMJudge:
    def test_judge_returns_parsed_score(self, reflector):
        score = reflector.judge("baseline artifact", "candidate artifact", "failure: agent skipped skill gate")
        assert score == pytest.approx(0.85)

    def test_judge_empty_traces_zero(self, reflector):
        assert reflector.judge("baseline", "candidate", "") == 0.0
        assert reflector.judge("baseline", "candidate", "  ") == 0.0

    def test_judge_short_traces_zero(self, reflector):
        # < 20 chars of trace = no signal, safe default
        assert reflector.judge("baseline", "candidate", "tiny") == 0.0

    def test_judge_clamps_out_of_range(self, judge_provider, reflector):
        judge_provider.judge_score = "7.3"
        assert reflector.judge("b", "c", "x" * 30) == 1.0
        judge_provider.judge_score = "-2"
        assert reflector.judge("b", "c", "x" * 30) == 0.0

    def test_judge_unparseable_zero(self, judge_provider, reflector):
        judge_provider.judge_score = "not a number at all"
        assert reflector.judge("b", "c", "x" * 30) == 0.0

    def test_judge_raises_returns_zero(self, judge_provider, reflector):
        def boom(prompt, system=None):
            raise RuntimeError("provider down")

        judge_provider.reflect = boom
        assert reflector.judge("b", "c", "x" * 30) == 0.0


class TestChunkedReflection:
    def test_reflect_sections_returns_improved_content(self, reflector):
        sections = [("protocol", "machine_protocol", "ORIGINAL A"), ("gate", "skill_gate", "ORIGINAL B")]
        improved = reflector.reflect_sections(sections, "failures here", "(none)")
        assert "machine_protocol" in improved
        assert "skill_gate" in improved
        assert "IMPROVED SECTION" in improved["machine_protocol"]

    def test_reflect_sections_strips_code_fences(self, judge_provider, reflector):
        """Models often wrap section output in ``` fences — must be stripped."""
        judge_provider.reflect = lambda prompt, system=None: "```markdown\nIMPROVED CONTENT\n```"

        sections = [("protocol", "a", "ORIG A")]
        improved = reflector.reflect_sections(sections, "failures")
        assert improved["a"] == "IMPROVED CONTENT"

    def test_reflect_sections_empty_content_skipped(self, reflector):
        sections = [("protocol", "empty_section", "   ")]
        improved = reflector.reflect_sections(sections, "failures")
        assert improved == {}

    def test_reflect_sections_failure_keeps_original(self, judge_provider, reflector):
        def boom(prompt, system=None):
            raise RuntimeError("provider down")

        judge_provider.reflect = boom
        sections = [("protocol", "a", "ORIG A")]
        improved = reflector.reflect_sections(sections, "failures")
        assert improved == {}  # failed calls skipped, original survives


class TestReplaceSectionContent:
    def test_replace_content_preserves_attrs(self):
        text = '<gate name="skill_gate" priority="P1">OLD</gate>'
        result = _replace_section_content(text, "skill_gate", "NEW CONTENT")
        assert '<gate name="skill_gate" priority="P1">NEW CONTENT</gate>' == result

    def test_replace_absent_section_noop(self):
        text = '<protocol name="a">X</protocol>'
        assert _replace_section_content(text, "missing", "NEW") == text

    def test_replace_multiple_sections(self):
        text = '<protocol name="a">X</protocol><verification name="b">Y</verification>'
        result = _replace_section_content(text, "b", "Z")
        assert '<verification name="b">Z</verification>' in result
        assert '<protocol name="a">X</protocol>' in result
