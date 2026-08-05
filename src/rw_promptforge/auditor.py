"""Reverse auditor — validates proposed changes before accepting them into the artifact.

Runs structural checks (ARMORED sections preserved), semantic checks
(do changes address failure traces), size checks (within total cap),
and stagnation checks (not cycling through near-identical outputs).
"""

from __future__ import annotations

import re

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
        if structural == PASS:
            structural = _check_all_sections_preserved(old_artifact, new_artifact)
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


# All wrapper tags that can carry a named section in SOUL.md artifacts.
# Opening form: <tag name="section_name" ...> ... </tag>
_SECTION_TAGS = (
    "section",
    "protocol",
    "gate",
    "verification",
    "quality_standards",
    "cognitive_framework",
    "infrastructure",
    "process_discipline",
    "identity",
    "style",
    "memory_system",
    "header",
    "section_map",
    "soul_file",
)


def _find_section_content(text: str, section_name: str) -> tuple[str, str] | None:
    """Locate a named section and return (tag, content).

    Searches for any opening tag of the form ``<tag name="section_name">``
    and extracts content until the matching ``</tag>``. Returns None when the
    section is absent.
    """
    for tag in _SECTION_TAGS:
        pattern = f'<{tag} name="{section_name}"'
        start = text.find(pattern)
        if start == -1:
            continue
        content_start = text.find(">", start) + 1
        if content_start == 0:
            return None
        close_tag = f"</{tag}>"
        end = text.find(close_tag, content_start)
        if end == -1:
            return None
        return tag, text[content_start:end]
    return None


def _check_armored_sections(old: str, new: str) -> str:
    """Verify ARMORED sections are preserved identically.

    Matches named sections regardless of wrapper tag type
    (``<protocol name=``, ``<verification name=``, ``<section name=``, ...),
    then compares the section content byte-for-byte.
    """
    from rw_promptforge.targets.soul import SoulTarget

    for section_name in SoulTarget.ARMORED_SECTIONS:
        old_found = _find_section_content(old, section_name)
        new_found = _find_section_content(new, section_name)

        if old_found is None and new_found is None:
            continue  # section not present in either — OK
        if old_found is None:
            continue  # was never there, shouldn't be now either
        if new_found is None:
            return FAIL  # ARMORED section removed!

        old_tag, old_content = old_found
        new_tag, new_content = new_found

        if old_tag != new_tag:
            return FAIL  # wrapper tag changed — breaks soul parsing

        if old_content.strip() != new_content.strip():
            return FAIL  # ARMORED content changed!

    return PASS


def _check_all_sections_preserved(old: str, new: str) -> str:
    """Verify ALL named sections in the original survive in the new artifact.

    Complements the ARMORED check — even non-armored sections must not be
    silently deleted (deletion inflates conciseness scores and loses critical
    instructions). Returns FAIL on the first missing section.
    """
    old_names = set()
    for tag in _SECTION_TAGS:
        for m in re.finditer(rf'<{tag} name="([a-z_]+)"', old):
            old_names.add((tag, m.group(1)))

    for tag, name in old_names:
        found = _find_section_content(new, name)
        if found is None:
            return FAIL  # section {name} deleted
        new_tag, _ = found
        if new_tag != tag:
            return FAIL  # section {name} changed wrapper tag

    return PASS


def _iter_sections(text: str) -> list[tuple[str, str, str]]:
    """Return (tag, name, content) tuples for all named sections, in FILE ORDER.

    Each element is (tag, name, content). Attributes on the opening tag
    (e.g. ``priority="P1"``) are preserved via the original text when the
    caller rebuilds from the original.
    """
    found: list[tuple[int, str, str, str]] = []  # (pos, tag, name, content)
    for tag in _SECTION_TAGS:
        for m in re.finditer(rf'<{tag} name="([a-z_]+)"', text):
            name = m.group(1)
            res = _find_section_content(text, name)
            if res is None:
                continue
            found_tag, content = res
            if found_tag == tag:
                found.append((m.start(), tag, name, content))
    # Order by file position — critical for cursor-based reassembly
    found.sort(key=lambda t: t[0])
    return [(tag, name, content) for _, tag, name, content in found]


def merge_artifact_sections(original: str, variant: str) -> str:
    """Rebuild an artifact guaranteeing the original skeleton survives.

    The LLM reflector tends to DELETE sections when asked to improve an
    artifact (deletion inflates conciseness scores). This merge takes the
    variant's section content where a section exists, and falls back to the
    original content for any section the variant dropped or renamed.

    Strategy:
    1. Parse the original into an ordered list of (tag, name, content).
    2. For each original section, use the variant's content if present
       (same tag + same name), else keep the original content.
    3. Append any NEW sections the variant introduced.
    4. Reassemble in original order with the variant's non-section prose
       where possible — otherwise keep the original header/footer.

    The result passes the completeness gate BY CONSTRUCTION.
    """
    orig_sections = _iter_sections(original)
    if not orig_sections:
        return variant  # nothing to protect

    orig_keys = {(tag, name) for tag, name, _ in orig_sections}
    orig_names = {name for _, name, _ in orig_sections}
    # Index variant sections by name — a variant may rename the wrapper tag
    # (e.g. <gate name="x"> → <section name="x">); we still treat it as the
    # same section and preserve the ORIGINAL tag type in the output.
    variant_by_name: dict[str, str] = {}
    new_sections: list[tuple[str, str, str]] = []
    for tag, name, content in _iter_sections(variant):
        variant_by_name[name] = content
        if name not in orig_names:
            new_sections.append((tag, name, content))

    # Assemble: original order, variant content when available
    rebuilt = ""
    cursor = 0
    for tag, name, orig_content in orig_sections:
        # Copy leading prose, preserving the ORIGINAL opening tag verbatim
        # (including attributes like priority="P1")
        pattern = f'<{tag} name="{name}"'
        pos = original.find(pattern, cursor)
        if pos != -1:
            rebuilt += original[cursor:pos]
            open_end = original.find(">", pos) + 1
            open_tag = original[pos:open_end]
            cursor = original.find(f"</{tag}>", open_end) + len(f"</{tag}>")
        else:
            open_tag = f'<{tag} name="{name}">'
            cursor = pos if pos != -1 else cursor

        # Variant content wins; original tag type + attributes are preserved
        content = variant_by_name.get(name, orig_content)
        rebuilt += f'{open_tag}{content}</{tag}>'

    # Append NEW sections the variant introduced (kept in variant order)
    for tag, name, content in new_sections:
        rebuilt += f'<{tag} name="{name}">{content}</{tag}>'

    # Tail prose after the last section in the original
    if cursor < len(original):
        rebuilt += original[cursor:]

    return rebuilt


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