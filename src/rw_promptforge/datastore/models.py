"""Data structures for the learning log, optimization results, and v2 extensions.

Includes multi-dimensional category scoring, convergence state, and
artifact metadata for the RefineStop v2 algorithm.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ── Failure Type Weights ──────────────────────────────────────────────

FAILURE_TYPE_WEIGHTS: dict[str, float] = {
    "protocol_violation": 2.0,  # agent ignored explicit instruction
    "correction": 1.5,          # user corrected agent
    "general": 1.0,             # default
    "tool_failure": 0.5,        # less actionable for prompt improvements
}

# ── Size & Round Budgets ──────────────────────────────────────────────

MAX_ARTIFACT_CHARS = 60000
"""""Maximum artifact size before head+tail truncation."""

SIZE_MULTIPLIER_CAP = 1.5
"""Max allowable growth ratio relative to the PREVIOUS ROUND's artifact size
(per-round cap, not cumulative from original). Each round may grow the
artifact by at most 1.5× the accepted size of the previous round."""

MAX_ROUNDS_CAP = 20
"""Hard ceiling on optimization iterations."""

MAX_EFFECTIVE_TRACES = 5
"""Number of failure traces surfaced to the reflector per round."""

SEVERITY_BUDGET_PER_ROUND = 10.0
"""Sum of trace multipliers allowed per round."""


# ── Utility Functions ─────────────────────────────────────────────────


def truncate_artifact(text: str, max_chars: int = MAX_ARTIFACT_CHARS) -> str:
    """Head+tail truncation for oversize artifacts.

    Preserves head and tail, inserts a truncation marker in the middle.
    """
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n... [TRUNCATED] ...\n" + text[-half:]


def sequence_similarity(a: str, b: str) -> float:
    """Character-level similarity ratio [0, 1] using SequenceMatcher.

    Replacement for hamming_distance — works on variable-length strings.
    """
    return difflib.SequenceMatcher(None, a, b).ratio()


def jaccard_similarity(a: str, b: str) -> float:
    """Token set overlap as a similarity score [0, 1].

    Replacement for cosine similarity when no embedding model is available.
    """
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def semantic_similarity(a, b) -> float:
    """Cosine similarity between two embedding vectors.

    Accepts numpy arrays, lists, or tuples of floats. Returns 0.0 when
    either vector has zero norm. Raises ValueError on length mismatch.
    numpy is imported lazily — token-based paths never pay the import cost.
    """
    if len(a) != len(b):
        msg = f"embedding dimension mismatch: {len(a)} vs {len(b)}"
        raise ValueError(msg)
    import numpy as np  # noqa: PLC0415 — lazy: ML-only dependency

    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0.0:
        return 0.0
    return float(np.dot(va, vb) / norm)


# ── Artifact Metadata ─────────────────────────────────────────────────


ARTIFACT_METADATA_FIELDS = (
    "name",
    "type",
    "total_lines",
    "total_chars",
    "region_count",
    "size_mb",
    "last_modified",
)

# (Not a dataclass to avoid import overhead for simple consumers)


def compute_artifact_meta(
    name: str,
    artifact_type: Literal["soul", "skill", "generic"],
    text: str,
    region_count: int = 0,
    last_modified: float = 0.0,
) -> dict:
    """Compute an ArtifactMeta dict from raw artifact text."""
    lines = text.splitlines()
    return {
        "name": name,
        "type": artifact_type,
        "total_lines": len(lines),
        "total_chars": len(text),
        "region_count": region_count,
        "size_mb": len(text) / (1024 * 1024),
        "last_modified": last_modified,
    }


# ── Category Scoring ──────────────────────────────────────────────────


@dataclass
class CategoryScores:
    """Multi-dimensional quality scores for a single artifact version."""

    structural_coherence: float = 0.0
    failure_coverage: float = 0.0
    conciseness: float = 0.0
    actionability: float = 0.0

    @property
    def composite(self) -> float:
        """Weighted composite score [0, 1]."""
        return (
            0.25 * self.structural_coherence
            + 0.35 * self.failure_coverage
            + 0.20 * self.conciseness
            + 0.20 * self.actionability
        )

    @property
    def weights(self) -> dict[str, float]:
        return {
            "structural_coherence": 0.25,
            "failure_coverage": 0.35,
            "conciseness": 0.20,
            "actionability": 0.20,
        }

    def as_dict(self) -> dict[str, float]:
        return {
            "structural_coherence": self.structural_coherence,
            "failure_coverage": self.failure_coverage,
            "conciseness": self.conciseness,
            "actionability": self.actionability,
            "composite": self.composite,
        }

    def __getitem__(self, key: str) -> float:
        return getattr(self, key)


# ── Multiplier Tracking ───────────────────────────────────────────────


@dataclass
class MultiplierEntry:
    """Directional improvement ratio per category for one round."""

    multipliers: dict[str, float]  # category_name → improvement ratio

    @property
    def overall(self) -> float:
        """Weighted-average overall multiplier."""
        if not self.multipliers:
            return 0.0
        w = CategoryScores().weights
        return sum(
            w.get(k, 0.2) * v for k, v in self.multipliers.items()
        )


def compute_multipliers(
    before: CategoryScores,
    after: CategoryScores,
    epsilon: float = 1e-6,
    cap: float = 5.0,
) -> MultiplierEntry:
    """Compute per-category improvement multipliers.

    multiplier[k] = (score_t - score_{t-1}) / max(score_{t-1}, epsilon)

    Results are capped to ±cap to prevent extreme values.
    """
    m: dict[str, float] = {}
    for key in ("structural_coherence", "failure_coverage", "conciseness", "actionability"):
        prev = getattr(before, key)
        curr = getattr(after, key)
        if abs(prev) < epsilon:
            m[key] = 0.0
        else:
            m[key] = max(-cap, min(cap, (curr - prev) / prev))
    return MultiplierEntry(multipliers=m)


# ── Convergence State ─────────────────────────────────────────────────


CONVERGENCE_THRESHOLD = 0.95
GAIN_THRESHOLD = 0.02
STABILITY_WINDOW = 2
REDUNDANCY_THRESHOLD = 0.3


@dataclass
class ConvergenceSignal:
    """State for one convergence signal."""

    name: str
    weight: float = 0.0
    value: float = 0.0
    stable_for: int = 0  # consecutive rounds meeting threshold
    active: bool = False


# ── Existing Models (v1 compatibility) ────────────────────────────────


@dataclass
class LearningLogEntry:
    """A single mutation attempt with its observed outcome."""

    attempted_change: str
    observed_outcome: str
    severity_before: float = 0.0
    severity_after: float = 0.0
    change_summary: str = ""
    # v2 extensions
    artifact_snippet: str = ""   # first 200 chars of artifact at this point
    categories: str = ""         # JSON-serialized CategoryScores
    multiplier: str = ""         # JSON-serialized MultiplierEntry


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
    severity: int = 0
    failure_type: str = "general"


@dataclass
class ContrastiveTraces:
    """Failure traces paired with nearby successes."""

    failures: list[FailureTrace]
    successes: list[str]
    root_cause: str = ""
    section_hint: str = ""
    learning_log: list[LearningLogEntry] = field(default_factory=list)


@dataclass
class OptimizeResult:
    """Immutable optimization outcome."""

    artifact: str
    rounds: int
    failures_found: int
    converged: bool
    failure_summary: str
    learning_log: list[LearningLogEntry]
    # v2 extensions
    composite_score: float = 0.0
    categories: str = ""  # JSON-serialized list of CategoryScores
    multipliers: str = ""  # JSON-serialized list of MultiplierEntry
    # v2.1 extensions
    frontier: list[Candidate] = field(default_factory=list)
    metric_type: str = "llm"
    metric_score: float = 0.0


# ── Severity Labels ───────────────────────────────────────────────────

SEVERITY_LABELS: dict[int, str] = {
    0: "LOW",
    1: "MEDIUM",
    2: "HIGH",
}


# ── v2.1 Frontier (data-driven optimizer style) ───────────────────────


class MetricType(str, Enum):
    """Pluggable programmatic evaluation metrics.

    Mirrors the Gemini data-driven optimizer's selectable metric palette:
    exact_match / rouge / bleu / tool_call_valid, plus the default LLM judge.
    All metrics are larger-is-better.
    """

    LLM = "llm"
    EXACT_MATCH = "exact_match"
    ROUGE_L = "rouge_l"
    ROUGE_2 = "rouge_2"
    BLEU = "bleu"
    TOOL_CALL_VALID = "tool_call_valid"


@dataclass
class Candidate:
    """One generated artifact variant with its evaluation scores."""

    artifact: str
    scores: CategoryScores = field(default_factory=CategoryScores)
    metric_score: float = 0.0  # programmatic metric vs gold target (0..1)
    size_delta: float = 0.0  # growth ratio vs original size (1.0 = unchanged)
    round_generated: int = 0

    @property
    def rank_score(self) -> float:
        """Combined ranking score: category composite + metric score.

        Weights favor the category composite (0.7) over the programmatic
        metric (0.3) — category scores capture structure/coverage/conciseness,
        while the metric captures task-specific behavioral fit.
        """
        return 0.7 * self.scores.composite + 0.3 * self.metric_score


@dataclass
class Frontier:
    """Ranked candidate frontier (Pareto-style, kept top-N by rank_score)."""

    candidates: list[Candidate] = field(default_factory=list)
    max_size: int = 5

    def add(self, candidate: Candidate) -> None:
        """Insert a candidate, then keep only the top-N by rank_score."""
        self.candidates.append(candidate)
        self.candidates.sort(key=lambda c: c.rank_score, reverse=True)
        self.candidates = self.candidates[: self.max_size]

    @property
    def best(self) -> Candidate | None:
        """Highest-ranked candidate, or None when empty."""
        return self.candidates[0] if self.candidates else None

    @property
    def spread(self) -> float:
        """Score spread between best and worst kept candidate [0, 1]."""
        if len(self.candidates) < 2:
            return 0.0
        return self.candidates[0].rank_score - self.candidates[-1].rank_score


@dataclass
class FewShotExample:
    """A labeled example for few-shot optimization (FPO-style).

    Two supported shapes, matching Gemini's few-shot optimizer:
    - Target-response: ``prompt`` + ``model_response`` + ``target_response``
    - Rubrics:         ``prompt`` + ``model_response`` + ``rubrics`` + ``rubrics_evaluations``
    """

    prompt: str
    model_response: str = ""
    target_response: str = ""
    rubrics: list[str] = field(default_factory=list)
    rubrics_evaluations: list[bool] = field(default_factory=list)

    @property
    def is_target_shape(self) -> bool:
        return bool(self.target_response)

    @property
    def is_rubrics_shape(self) -> bool:
        return bool(self.rubrics) and bool(self.rubrics_evaluations)

    def rubric_hit_rate(self) -> float:
        """Fraction of rubrics met (0..1), 0.0 when no rubrics present."""
        if not self.rubrics_evaluations:
            return 0.0
        return sum(self.rubrics_evaluations) / len(self.rubrics_evaluations)