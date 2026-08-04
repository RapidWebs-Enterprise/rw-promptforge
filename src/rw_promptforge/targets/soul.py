"""Target definition for SOUL.md optimization."""

from __future__ import annotations

from pathlib import Path


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

        Returns dict of section_name → section_content.
        Returns empty dict if no section tags found.
        """
        result: dict[str, str] = {}
        artifact = self.content

        for section_name in self.ARMORED_SECTIONS:
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
