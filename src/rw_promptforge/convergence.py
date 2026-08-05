"""Convergence detection and redundancy checking for the RefineStop v2 algorithm.

Uses multi-signal scoring based on the reverse audit's corrected math:
- Jaccard similarity for semantic change (NOT cosine — no embeddings needed)
- SequenceMatcher for stagnation (NOT hamming — works on variable-length)
- Tracking fix rate correctly (low fix rate = convergence signal)
"""

from __future__ import annotations

from rw_promptforge.datastore.models import (
    LearningLogEntry,
    CategoryScores,
    MultiplierEntry,
    jaccard_similarity,
    sequence_similarity,
    STABILITY_WINDOW,
    GAIN_THRESHOLD,
    REDUNDANCY_THRESHOLD,
)


def convergence_score(history: list[LearningLogEntry]) -> float:
    """Compute a multi-signal convergence score [0.0, 1.0].

    Three signals combined with weights:
    - 0.4 Severity trend (stable severity = plateau)
    - 0.3 Size stability (artifact size not changing)
    - 0.3 Fix rate (low fix rate = converged — nothing left to fix)
    """
    if len(history) < 2:
        return 0.0

    recent = history[-3:]

    # Signal 1: Severity trend (stable = plateau = converged)
    # Only counts if we have enough data to detect a trend
    severities = [e.severity_after for e in recent]

    # If severity is 0 across the board, nothing was ever wrong — not convergence yet
    if all(s == 0 for s in severities):
        severity_score = 0.1  # low score, keep going
    elif all(s >= severities[0] for s in severities):
        severity_score = 0.4  # stable = converged
    else:
        severity_score = 0.0  # still improving

    # Signal 2: Size stability — use artifact_snippet length as proxy
    if recent[0].artifact_snippet:
        sizes = [len(e.artifact_snippet) for e in recent]
        size_stable = max(sizes) - min(sizes) < 100
    else:
        # Fallback: use change_summary length
        sizes = [len(e.change_summary) for e in recent]
        size_stable = max(sizes) - min(sizes) < 50
    size_score = 0.3 if size_stable else 0.0

    # Signal 3: Fix rate — LOW rate = converged (nothing left to improve)
    traces_fixed = sum(
        1 for e in recent if e.observed_outcome == "improvement"
    )
    fix_rate = traces_fixed / len(recent)
    # CORRECTED: low fix rate = convergence signal (reverse audit fix)
    fix_score = 0.3 if fix_rate < 0.3 else 0.0

    score = severity_score + size_score + fix_score
    return min(score, 1.0)


def is_converged(
    history: list[LearningLogEntry],
    multipliers: list[MultiplierEntry] | None = None,
    threshold: float = 0.8,
) -> bool:
    """Decide whether the optimization loop should stop.

    Returns True when:
    - Convergence score >= ``threshold`` (hard stop, default 0.8), OR
    - 2+ signals active in soft zone (score >= 0.6 + stagnant outcome)
    """
    if len(history) < 2:
        return False

    score = convergence_score(history)

    # Hard stop
    if score >= threshold:
        return True

    # Soft stop: 2+ signals active
    signals_active = 0
    if score >= 0.6:
        signals_active += 1

    recent = history[-3:]
    non_improvement = sum(
        1 for e in recent if e.observed_outcome != "improvement"
    )
    if non_improvement >= 2:
        signals_active += 1

    return signals_active >= 2


def check_redundancy(history: list[LearningLogEntry]) -> bool:
    """Detect diminishing returns — when improvements become redundant.

    Uses the textual relaxation pattern: edit magnitude should follow
    exponential decay. When each round adds < REDUNDANCY_THRESHOLD (30%)
    of the previous round's change, we're in a diminishing returns regime.

    CORRECTED: Uses SequenceMatcher instead of hamming_distance.
    """
    if len(history) < 3:
        return False

    # Compute consecutive similarity scores (lower = more change)
    similarities = []
    for i in range(len(history) - 1):
        # Compare artifact snippets stored in the entries
        a = history[i].artifact_snippet or history[i].change_summary
        b = history[i + 1].artifact_snippet or history[i + 1].change_summary
        sim = sequence_similarity(a, b)
        similarities.append(sim)

    if len(similarities) < 2:
        return False

    # Check exponential decay: each round should have less change
    # i.e., similarities should be INCREASING (converging)
    recent = similarities[-3:] if len(similarities) >= 3 else similarities
    for i in range(1, len(recent)):
        # If similarity dropped (more change) vs previous, not redundant
        if recent[i] < recent[i - 1] * (1 - REDUNDANCY_THRESHOLD):
            return False

    # If ALL recent pairs show decreasing change, it's redundant
    change_rate = sum(recent) / len(recent)
    return change_rate > 0.85  # high similarity overall = redundant


def check_semantic_stability(
    current: str,
    proposed: str,
    threshold: float = 0.95,
) -> bool:
    """Check if consecutive versions are semantically similar.

    Uses Jaccard token similarity (no embeddings needed).
    Added as reverse audit fix for the unimplementable cosine_sim.
    """
    return jaccard_similarity(current, proposed) >= threshold


def check_gain_saturation(
    prev_scores: CategoryScores | None,
    current_scores: CategoryScores,
    threshold: float = GAIN_THRESHOLD,
) -> bool:
    """Check if the expected gain from another round is negligible.

    Returns True when composite score changed less than threshold.
    """
    if prev_scores is None:
        return False
    return abs(current_scores.composite - prev_scores.composite) < threshold


def format_convergence_report(
    history: list[LearningLogEntry],
    multipliers: list[MultiplierEntry] | None = None,
) -> str:
    """Format a human-readable convergence status report."""
    score = convergence_score(history)
    lines = [
        f"Convergence Score: {score:.2f}/1.0",
        f"Converged: {'YES' if is_converged(history, multipliers) else 'NO'}",
        f"Redundant: {'YES' if check_redundancy(history) else 'NO'}",
        f"History length: {len(history)}",
    ]

    if multipliers:
        for i, m in enumerate(multipliers):
            if i >= 3:  # last 3
                break
            lines.append(f"  Round {len(multipliers)-i}: {m.overall:+.2%}")

    return "\n".join(lines)