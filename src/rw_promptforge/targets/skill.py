"""Target definition for Skill optimization."""

from __future__ import annotations

from pathlib import Path


class SkillTarget:
    """Represents a skill SKILL.md file as an optimization target.

    Skills are YAML-frontmatter + markdown instruction sets.
    Optimization focuses on:
      - Instruction clarity and completeness
      - Missing steps or pitfalls
      - Outdated commands or tool names
      - Trigger/context matching accuracy
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._content = ""
        self._frontmatter: dict[str, str] = {}
        self._body = ""

    @property
    def content(self) -> str:
        if not self._content:
            self._content = self.path.read_text()
        return self._content

    @property
    def frontmatter(self) -> dict[str, str]:
        """Parse YAML frontmatter from the skill file."""
        if not self._frontmatter and self.content:
            self._parse()
        return self._frontmatter

    @property
    def body(self) -> str:
        """Return the markdown body (everything after frontmatter)."""
        if not self._body and self.content:
            self._parse()
        return self._body

    def _parse(self) -> None:
        """Extract frontmatter + body."""
        content = self.content.lstrip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                import yaml
                self._frontmatter = yaml.safe_load(parts[1]) or {}
                self._body = parts[2].strip()
            else:
                self._body = content
        else:
            self._body = content

    @property
    def name(self) -> str:
        return self.frontmatter.get("name", self.path.stem)

    @property
    def triggers(self) -> list[str]:
        return self.frontmatter.get("triggers", [])

    def estimate_tokens(self) -> int:
        return len(self.content) // 4