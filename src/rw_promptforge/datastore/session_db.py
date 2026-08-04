"""Access Hermes session_db for extracting training data and failure traces.

Reads the SQLite database at ~/.hermes/session_db/ (or custom path) to find:
  - Sessions where a given skill was loaded
  - Tasks that succeeded vs. failed
  - User corrections that indicate a skill deficiency
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionMatch:
    """A session relevant to a skill's optimization."""

    session_id: str
    title: str
    when: str
    role: str
    content: str


class SessionDBReader:
    """Read-only accessor for the Hermes session database."""

    DEFAULT_PATH = Path.home() / ".hermes" / "session_db" / "sessions.db"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_PATH

    def exists(self) -> bool:
        return self.db_path.is_file()

    def find_sessions_with_skill(self, skill_name: str, limit: int = 20) -> list[SessionMatch]:
        """Find sessions where a given skill was referenced."""
        if not self.exists():
            return []
        # TODO: query once we know the actual session_db schema
        return []

    def find_corrections_after_skill_use(self, skill_name: str, limit: int = 10) -> list[SessionMatch]:
        """Find user corrections that happened after loading a skill.

        These are prime optimization targets. The pattern:
          1. Skill loaded
          2. Agent did something wrong
          3. User corrected it

        Returns session matches where this pattern occurred.
        """
        if not self.exists():
            return []
        return []