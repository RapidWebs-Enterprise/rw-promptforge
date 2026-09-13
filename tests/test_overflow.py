"""Tests for the overflow-handling strategies (S1 fail-loud, S2 budget-retry).

Regression guard for the 2026-08-05 soul-refine incident: oversized LLM
refinement output was silently middle-spliced with "... [TRUNCATED] ..."
markers, permanently destroying content. These tests pin the
replacement behavior: never splice, never emit the marker.
"""

from __future__ import annotations

import pytest

from rw_promptforge.reflector.engine import BudgetExceededError, Reflector

MARKER = "... [TRUNCATED] ..."


class StubProvider:
    """Minimal provider stub honoring the reflect(prompt=..., system=...) contract."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def reflect(self, prompt: str, system: str = "") -> str:
        self.calls.append(prompt)
        if not self._responses:
            raise AssertionError("StubProvider exhausted — unexpected extra call")
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# reflect() — whole-artifact path
# ---------------------------------------------------------------------------


class TestReflectOverflow:
    def test_retry_strategy_compresses_oversized_output(self) -> None:
        """S2: oversized first response triggers a compression retry that fits."""
        oversized = "x" * 500
        compressed = "short refined result"
        provider = StubProvider([oversized, compressed])
        r = Reflector(provider, on_overflow="retry")

        result = r.reflect("artifact", "ctx", size_budget=100)

        assert result == compressed
        assert len(provider.calls) == 2
        assert "exceeding the" in provider.calls[1]
        assert MARKER not in result

    def test_retry_exhaustion_raises_budget_exceeded(self) -> None:
        """S2 fallback: when every retry stays oversized, raise — never splice."""
        provider = StubProvider(["x" * 500] * 5)
        r = Reflector(provider, on_overflow="retry")

        with pytest.raises(BudgetExceededError) as exc_info:
            r.reflect("artifact", "ctx", size_budget=100)

        assert exc_info.value.actual_chars > exc_info.value.budget_chars

    def test_fail_strategy_raises_immediately(self) -> None:
        """S1: fail mode raises on first oversize with no retry call."""
        provider = StubProvider(["x" * 500])
        r = Reflector(provider, on_overflow="fail")

        with pytest.raises(BudgetExceededError):
            r.reflect("artifact", "ctx", size_budget=100)

        assert len(provider.calls) == 1

    def test_undersized_output_passes_through(self) -> None:
        provider = StubProvider(["fine result"])
        r = Reflector(provider, on_overflow="retry")

        assert r.reflect("artifact", "ctx", size_budget=100) == "fine result"
        assert len(provider.calls) == 1

    def test_no_budget_skips_enforcement(self) -> None:
        """size_budget=0 disables enforcement entirely (legacy behavior)."""
        provider = StubProvider(["x" * 500])
        r = Reflector(provider, on_overflow="fail")

        assert r.reflect("artifact", "ctx", size_budget=0) == "x" * 500

    def test_invalid_strategy_rejected(self) -> None:
        with pytest.raises(ValueError, match="on_overflow"):
            Reflector(StubProvider([]), on_overflow="splice")


# ---------------------------------------------------------------------------
# reflect_sections() — chunked path (the one that corrupted SOUL.md)
# ---------------------------------------------------------------------------


class TestReflectSectionsOverflow:
    def _sections(self) -> list[tuple[str, str, str]]:
        return [("s1", "Section One", "original content one")]

    def test_oversized_section_retries_and_fits(self) -> None:
        provider = StubProvider(["x" * 500, "compressed section"])
        r = Reflector(provider, on_overflow="retry")

        results = r.reflect_sections(self._sections(), failure_traces="", size_budget=100, max_workers=1)

        assert results == {"Section One": "compressed section"}
        assert MARKER not in results["Section One"]

    def test_fail_mode_keeps_original_section(self, capsys: pytest.CaptureFixture[str]) -> None:
        """S1 at section level: loud warning + original content preserved."""
        provider = StubProvider(["x" * 500])
        r = Reflector(provider, on_overflow="fail")

        results = r.reflect_sections(self._sections(), failure_traces="", size_budget=100, max_workers=1)

        assert results == {"Section One": "original content one"}
        assert MARKER not in results["Section One"]
        err = capsys.readouterr().err
        assert "Section One" in err
        assert "keeping original section" in err

    def test_retry_exhaustion_keeps_original_section(self) -> None:
        """Retry mode that never converges degrades to keep-original, not splice."""
        provider = StubProvider(["x" * 500] * 5)
        r = Reflector(provider, on_overflow="retry")

        results = r.reflect_sections(self._sections(), failure_traces="", size_budget=100, max_workers=1)

        assert results == {"Section One": "original content one"}
        assert MARKER not in results["Section One"]
