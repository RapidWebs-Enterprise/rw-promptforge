"""Target definition for SOUL.md optimization."""

from __future__ import annotations

from pathlib import Path


# All wrapper tags that can carry a named section in SOUL.md artifacts.
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


class SoulTarget:
    """Represents a SOUL.md file as an optimization target.

    SOUL.md is structured: sections, protocols, priorities.
    The optimizer needs to know which sections are mutable vs. immutable.
    """

    ARMORED_SECTIONS = {
        "machine_protocol",
        "project_registry",
        "skill_gate",
        "budget_guards",
        "reality_check",
        "process_level_discipline",
    }
    """Sections that must NEVER be modified. These are safety-critical."""

    OPTIMIZABLE_SECTIONS = {
        "identity",
        "style",
        "communication_style",
        "core_ethos",
        "modern_prompting",
        "anti_hallucination",
        "refactoring_patterns",
        "session_protocol",
        "coding_standards",
        "debugging_protocol",
    }
    """Sections that can be optimized for clarity, conciseness, and effectiveness."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._content = ""

    @property
    def content(self) -> str:
        if not self._content:
            self._content = self.path.read_text()
        return self._content

    def estimate_tokens(self) -> int:
        """Rough token count (4 chars ≈ 1 token)."""
        return len(self.content) // 4

    def extract_armored_sections(self) -> dict[str, str]:
        """Extract ARMORED section contents as text.

        Uses tag-aware matching (handles <protocol>, <gate>, <verification>,
        etc. — not just <section>). Returns dict of section_name → section_content.
        Returns empty dict if no armored sections found.
        """
        result: dict[str, str] = {}
        artifact = self.content

        for section_name in self.ARMORED_SECTIONS:
            found = _find_section_content(artifact, section_name)
            if found is not None:
                _tag, content = found
                result[section_name] = content.strip()

        return result