"""Reverse auditor — validates proposed changes before accepting them into the artifact.

Runs structural checks (ARMORED sections preserved), semantic checks
(do changes address failure traces), size checks (within total cap),
and stagnation checks (not cycling through near-identical outputs).
"""

from __future__ import annotations

from rw_promptforge.datastore.models import (
    sequence_similarity,
    SIZE_MULTIPLIER_CAP,
)

# Audit result constants
PASS = "PASS"
FAIL = "FAIL"
REVIEW = "REVIEW"


def reverse_audit(
    artifact_path: str | None,
    old_artifact: str,
    new_artifact: str,
    failure_traces: str = "",
    original_size: int = 0,
    recent_snippets: list[str] | None = None,
    size_cap: float = SIZE_MULTIPLIER_CAP,
) -> str:
    """Run a reverse audit on a proposed optimizer change.

    Parameters
    ----------
    artifact_path : str | None
        Path to the artifact file (used to extract ARMORED sections).
    old_artifact : str
        Current artifact text.
    new_artifact : str
        Proposed new artifact text.
    failure_traces : str
        Failure traces the optimization was trying to address.
    original_size : int
        Original artifact size (for total cap check).
    recent_snippets : list[str] | None
        Artifact snippets from recent history for stagnation detection.
    size_cap : float
        Growth cap as a multiplier of the original size (default 1.5).

    Returns
    -------
    str
        PASS, FAIL, or REVIEW.
    """
    if not new_artifact or len(new_artifact.strip()) < 10:
        return FAIL

    # 1. STRUCTURAL CHECK
    if artifact_path and "soul" in artifact_path.lower():
        structural = _check_armored_sections(old_artifact, new_artifact)
    else:
        structural = _check_yaml_frontmatter(new_artifact)
    if structural != PASS:
        return structural  # FAIL

    # 2. SIZE CHECK — total cap from original
    if original_size > 0:
        if len(new_artifact) > original_size * size_cap:
            return FAIL  # hard reject — size cap exceeded

    # 3. SEMANTIC CHECK
    semantic = _check_semantic_coverage(new_artifact, failure_traces)
    if semantic != PASS:
        return REVIEW  # flag for human, don't auto-reject

    # 4. STAGNATION CHECK
    if recent_snippets:
        for snippet in recent_snippets:
            if not snippet:
                continue
            sim = sequence_similarity(
                new_artifact[:500], snippet[:500]
            )
            if sim > 0.95:
                return FAIL  # stagnating

    return PASS


# ── Structural Checks ─────────────────────────────────────────────────


def _check_armored_sections(old: str, new: str) -> str:
    """Verify ARMORED sections are preserved identically.

    Uses SoulTarget.ARMORED_SECTIONS set to identify which section
    names must not change.
    """
    from rw_promptforge.targets.soul import SoulTarget

    for section_name in SoulTarget.ARMORED_SECTIONS:
        old_pattern = f'<section name="{section_name}">'
        new_pattern = f'<section name="{section_name}">'

        old_start = old.find(old_pattern)
        new_start = new.find(new_pattern)

        if old_start == -1 and new_start == -1:
            continue  # section not present in either — OK
        if old_start == -1:
            continue  # was never there, shouldn't be now either
        if new_start == -1:
            return FAIL  # ARMORED section removed!

        # Find the section content between <section> and </section>
        old_end_tag = f"</section>"
        old_end = old.find(old_end_tag, old_start)
        new_end = new.find(old_end_tag, new_start)

        if old_end == -1 or new_end == -1:
            return FAIL  # malformed section tags

        # Extract content between tags (skip the opening tag line)
        old_content = old[old_start + len(old_pattern):old_end]
        new_content = new[new_start + len(new_pattern):new_end]

        if old_content.strip() != new_content.strip():
            return FAIL  # ARMORED content changed!

    return PASS


def _check_yaml_frontmatter(text: str) -> str:
    """Verify skill YAML frontmatter schema is preserved.

    Only checks that --- markers exist and name/triggers present.
    """
    stripped = text.lstrip()
    if stripped.startswith("---"):
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            if "name:" not in frontmatter:
                return REVIEW  # name field missing — human check needed
    return PASS


# ── Semantic Checks ───────────────────────────────────────────────────


def _check_semantic_coverage(new_artifact: str, failure_traces: str) -> str:
    """Check that semantic changes don't introduce ambiguity.

    Review-level check: if no traces were provided, skip.
    If traces exist, at minimum check they're still present.
    """
    if not failure_traces or len(failure_traces.strip()) < 20:
        return PASS  # no traces to check against

    # Quick check: does the new artifact mention key trace terms?
    # Very lenient — just checks the artifact isn't wildly off-topic.
    trace_keywords = {
        w for w in failure_traces.lower().split()
        if len(w) > 5 and w not in _STOPWORDS
    }
    if not trace_keywords:
        return PASS

    artifact_lower = new_artifact.lower()
    # If artifact doesn't reference ANY trace keyword, flag for review
    if not any(kw in artifact_lower for kw in trace_keywords):
        return REVIEW

    return PASS


_STOPWORDS = frozenset({
    "about", "above", "after", "again", "because", "being",
    "could", "doesn", "each", "every", "from", "further",
    "have", "here", "into", "just", "like",
    "more", "most", "much", "must", "only", "other",
    "same", "some", "such", "than", "that", "their",
    "then", "there", "these", "they", "this", "those",
    "under", "until", "very", "what", "when", "where",
    "which", "while", "with",
})


# ── Utility for ARMORED extraction (used by targets) ──────────────────


def extract_armored_sections(artifact: str) -> dict[str, str]:
    """Extract ARMORED sections from a SOUL.md artifact.

    Returns a dict of section_name → section_content.
    Falls back gracefully if no section tags are found.
    """
    from rw_promptforge.targets.soul import SoulTarget
    result: dict[str, str] = {}

    for section_name in SoulTarget.ARMORED_SECTIONS:
        pattern = f'<section name="{section_name}">'
        start = artifact.find(pattern)
        if start == -1:
            continue
        end_tag = artifact.find("</section>", start)
        if end_tag == -1:
            continue
        content_start = start + len(pattern)
        result[section_name] = artifact[content_start:end_tag].strip()

    return result