"""Data structures for the learning log and optimization results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LearningLogEntry:
    """A single mutation attempt with its observed outcome.

    Modeled after Darwinian Evolver's LearningLogEntry.
    """

    attempted_change: str
    """What the mutator tried to do (concise diff-style description)."""

    observed_outcome: str
    """What actually happened — improvement, regression, or neutral."""

    severity_before: int = 0
    """Failure severity before the change (0=low, 1=medium, 2=high)."""

    severity_after: int = 0
    """Failure severity after the change."""

    change_summary: str = ""
    """Structured summary of the change for LLM consumption."""


@dataclass
class FailureTrace:
    """A real-world failure where the agent got something wrong."""

    session_id: str
    timestamp: float
    what_happened: str
    user_correction: str
    agent_response: str = ""
    skill_name: str = ""
    context: str = ""
    severity: int = 0  # 0=low, 1=medium, 2=high
    failure_type: str = "general"  # For weighted sampling


@dataclass
class ContrastiveTraces:
    """Failure traces paired with nearby successes."""

    failures: list[FailureTrace]
    successes: list[str]
    root_cause: str = ""
    section_hint: str = ""
    learning_log: list[LearningLogEntry] = field(default_factory=list)


# Failure type weights for sampling
# Higher weight = more likely to be sampled
DEFAULT_FAILURE_TYPE_WEIGHTS: dict[str, float] = {
    "protocol_violation": 2.0,  # Most important
    "general": 1.0,
    "tool_failure": 0.5,  # Less actionable for prompt improvements
}

# Severity labels for output
SEVERITY_LABELS: dict[int, str] = {
    0: "LOW",
    1: "MEDIUM",
    2: "HIGH",
}
