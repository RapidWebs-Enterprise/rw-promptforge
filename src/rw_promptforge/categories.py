"""4-category multi-dimensional scoring for optimized artifacts.

Each optimized version is scored across four dimensions. The composite
score weights categories by importance and drives the convergence decision.
"""

from __future__ import annotations

import re
import json

from rw_promptforge.datastore.models import (
    CategoryScores,
    compute_multipliers,
    MultiplierEntry,
)


def score_categories(
    artifact: str,
    failure_traces: str = "",
    _structural_callback=None,
    _actionability_callback=None,
) -> CategoryScores:
    """Score an artifact across all 4 categories.

    Parameters
    ----------
    artifact : str
        The optimized artifact text.
    failure_traces : str
        Formatted failure traces used to drive the optimization
        (used for failure coverage scoring).
    _structural_callback / _actionability_callback :
        For testing — override the LLM judge calls.

    Returns
    -------
    CategoryScores
        Scores for each dimension (0.0–1.0 each).
    """
    return CategoryScores(
        structural_coherence=_score_structural(artifact, _structural_callback),
        failure_coverage=_score_failure_coverage(artifact, failure_traces),
        conciseness=_score_conciseness(artifact),
        actionability=_score_actionability(artifact, _actionability_callback),
    )


# ── C1: Structural Coherence ──────────────────────────────────────────


def _score_structural(artifact: str, callback=None) -> float:
    """Score structural coherence.

    Uses a simple heuristic (section count, hierarchy depth) as a
    deterministic baseline. An LLM judge prompt can be swapped in via
    the callback for higher accuracy.
    """
    if callback:
        return callback(artifact)

    lines = artifact.splitlines()
    sections = [l for l in lines if l.startswith("## ")]
    sub_sections = [l for l in lines if l.startswith("### ")]

    if not sections:
        return 0.3  # no structure

    # Depth variety is good
    depth_ok = 1.0 if sub_sections else 0.5
    # More sections = more structure, capped
    section_score = min(1.0, len(sections) / 15.0)

    return (section_score + depth_ok) / 2.0


# ── C2: Failure Pattern Coverage ──────────────────────────────────────


def _score_failure_coverage(artifact: str, failure_traces: str) -> float:
    """Score how well the artifact addresses documented failure patterns.

    Extracts key terms from failure traces and measures coverage in
    the artifact text via token overlap.
    """
    if not failure_traces or len(failure_traces.strip()) < 20:
        return 0.5  # no traces = neutral

    # Extract significant tokens from traces
    trace_words = set(failure_traces.lower().split())
    # Focus on content words (skip very short/common)
    trace_keywords = {
        w for w in trace_words if len(w) > 4 and w not in _STOPWORDS
    }

    if not trace_keywords:
        return 0.5

    # Check how many appear in the artifact
    artifact_lower = artifact.lower()
    covered = sum(1 for w in trace_keywords if w in artifact_lower)
    ratio = covered / len(trace_keywords)

    return min(1.0, ratio * 1.5)  # bonus for dense coverage


_STOPWORDS = frozenset({
    "about", "above", "after", "again", "because", "being", "below",
    "could", "doesn", "does", "don", "down", "each", "every",
    "from", "further", "have", "here", "into", "just", "like",
    "more", "most", "much", "must", "only", "other", "over",
    "same", "some", "such", "than", "that", "their", "them",
    "then", "there", "these", "they", "this", "those", "through",
    "under", "until", "very", "what", "when", "where", "which",
    "while", "with", "your",
})


# ── C3: Conciseness ───────────────────────────────────────────────────


def _score_conciseness(artifact: str) -> float:
    """Score conciseness — information density vs. verbosity.

    Heuristic: penalize artifacts that are very long while measuring
    reasonable structural token efficiency.

    Counts BOTH markdown headers (## ) and named XML-style section tags
    (<tag name="...">) so this works correctly for both skill.md files
    (markdown headers) and SOUL.md files (named sections with tags).
    """
    lines = artifact.splitlines()
    total_words = sum(len(l.split()) for l in lines if l.strip())
    if total_words == 0:
        return 0.0

    # Token efficiency: sections / thousand words
    # Count BOTH markdown headers AND named section tags
    import re
    md_sections = len([l for l in lines if l.startswith("## ")])
    tag_sections = len(re.findall(r'<[a-z_]+ name="[a-z_]+"', artifact))
    sections = md_sections + tag_sections
    if sections > 0:
        density = sections / (total_words / 1000.0)
    else:
        density = 0

    # Ideal: 3-10 sections per 1000 words
    if density < 2:
        density_score = density / 2.0  # below ideal
    elif density > 15:
        density_score = 15.0 / density  # too dense
    else:
        density_score = 1.0  # sweet spot

    # Size penalty: very long artifacts lose points
    size_penalty = max(0.0, 1.0 - (total_words - 3000) / 10000.0)

    return (density_score * 0.6 + size_penalty * 0.4)


# ── C4: Actionability ─────────────────────────────────────────────────


def _score_actionability(artifact: str, callback=None) -> float:
    """Score actionability — how directly executable are the instructions.

    Uses imperative verb density and step-like formatting as heuristics.
    """
    if callback:
        return callback(artifact)

    lines = artifact.splitlines()

    # Count imperative verbs at start of lines
    imperative_verbs = {"use", "run", "call", "check", "do", "set",
                        "load", "add", "remove", "update", "create",
                        "delete", "write", "read", "list", "find",
                        "enable", "disable", "start", "stop", "restart",
                        "verify", "validate", "confirm", "ensure",
                        "never", "always", "must", "should", "avoid"}
    action_lines = 0
    for line in lines:
        first_word = line.strip().lower().split(" ")[0] if line.strip() else ""
        if first_word in imperative_verbs:
            action_lines += 1

    # Count numbered steps
    step_lines = sum(1 for l in lines if l.strip().startswith(("1.", "2.", "3.",
                      "4.", "5.", "6.", "7.", "8.", "9.", "0.", "- ")))

    # Score: 0.3 base + per-action bonus
    action_ratio = action_lines / max(len(lines), 1)
    has_steps = 0.3 if step_lines > 0 else 0.0

    score = 0.3 + min(action_ratio * 2.0, 0.4) + has_steps
    return min(score, 1.0)


# ── Public Convenience Functions ──────────────────────────────────────


def format_category_report(
    before: CategoryScores,
    after: CategoryScores,
) -> str:
    """Format a human-readable category comparison report."""
    multipliers = compute_multipliers(before, after)
    lines = ["Score Changes:"]
    for key in ("structural_coherence", "failure_coverage", "conciseness", "actionability"):
        b = getattr(before, key)
        a = getattr(after, key)
        m = multipliers.multipliers.get(key, 0)
        arrow = "↑" if m > 0.02 else ("↓" if m < -0.02 else "→")
        lines.append(
            f"  {key.replace('_', ' ').title():30s} "
            f"{b:.2f} → {a:.2f}  ({arrow} {m:+.1%})"
        )
    lines.append(f"  {'Composite':30s} {before.composite:.2f} → {after.composite:.2f}")
    return "\n".join(lines)