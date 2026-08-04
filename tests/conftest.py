"""Test fixtures for optimizer tests — stub LLM, temp files, etc."""

import pytest


@pytest.fixture
def stub_provider():
    """Provider that returns canned text without any HTTP calls.

    Each call to reflect() returns the artifact text with a fixed
    suffix appended, simulating improvement across rounds.
    """

    class StubProvider:
        def __init__(self):
            self.calls = []
            self._responses = [
                "IMPROVED: added explicit instruction",
                "FURTHER IMPROVED: added verification step",
                "FINAL: polished clarity",
            ]

        def reflect(self, prompt: str, system: str | None = None) -> str:
            self.calls.append({"prompt": prompt[:100], "system": system})
            idx = len(self.calls) - 1
            if idx < len(self._responses):
                return self._responses[idx]
            return self._responses[-1]

        def close(self):
            pass

    return StubProvider()


@pytest.fixture
def failing_eval_command():
    """Shell command that always fails — good for testing iteration."""
    return "exit 1"


@pytest.fixture
def passing_eval_command():
    """Shell command that always passes — good for testing convergence."""
    return "exit 0"


@pytest.fixture
def temp_skill(tmp_path):
    """Write a minimal skill to a temp file for optimizer tests."""

    skill_path = tmp_path / "test_skill.md"
    skill_path.write_text(
        "---\nname: test-skill\ntriggers:\n  - test trigger\n---\n\n"
        "# Test Skill\n\n"
        "Step 1: Do something.\n"
        "Step 2: Verify.\n"
    )
    return str(skill_path)
