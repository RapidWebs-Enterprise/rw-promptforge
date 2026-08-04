"""Session database reader — extracts real failure traces for optimization.

The key insight: instead of asking "does this file have the right sections?",
we ask "did this skill/SOUL.md prevent the agent from failing in real usage?"

Queries state.db for:
- Sessions where user corrected the agent after loading a skill
- Tool call failures when a skill was loaded
- Protocol violations (agent did X despite SOUL.md saying don't do X)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


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


class SessionDBReader:
    """Read Hermes session_db for real failure traces."""

    DEFAULT_PATH = Path.home() / ".hermes" / "state.db"

    CORRECTION_PATTERNS = [
        "%thats not what%",
        "%that's not what%",
        "%not what i%",
        "%you were supposed%",
        "%you should have%",
        "%you did%wrong%",
        "%actually%should%",
        "%no, %",
        "%wrong%",
        "%you just%",
        "%you committed%",
        "%you were supposed to%",
        "%dont%commit%",
        "%don't%commit%",
        "%never%touch%",
    ]

    PROTOCOL_VIOLATION_PATTERNS = [
        "%committed to hermes%",
        "%committed in hermes%",
        "%modified hermes source%",
        "%touched nousresearch%",
        "%skipped verification%",
        "%claimed done%",
        "%without verifying%",
    ]

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_PATH

    def exists(self) -> bool:
        return self.db_path.is_file()

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run a query and return list of dicts."""
        if not self.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def find_corrections(
        self, skill_name: str | None = None, limit: int = 10
    ) -> list[FailureTrace]:
        """Find sessions where user corrected the agent.

        These are the gold-mine for skill optimization:
        the user explicitly said "you did X wrong" after the agent
        used a skill (or should have used one).
        """
        traces = []
        for pattern in self.CORRECTION_PATTERNS:
            rows = self._query(
                """
                SELECT DISTINCT m.session_id, m.timestamp, m.content
                FROM messages m
                WHERE m.role = 'user'
                AND m.content LIKE ?
                ORDER BY m.timestamp DESC
                LIMIT ?
                """,
                (pattern, limit),
            )
            for row in rows:
                # Get the assistant's response before this correction
                prev = self._query(
                    """
                    SELECT content FROM messages
                    WHERE session_id = ? AND role = 'assistant'
                    AND timestamp < ?
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (row["session_id"], row["timestamp"]),
                )
                traces.append(
                    FailureTrace(
                        session_id=row["session_id"],
                        timestamp=row["timestamp"],
                        what_happened=prev[0]["content"][:500] if prev else "",
                        user_correction=row["content"][:500],
                        skill_name=skill_name or "",
                    )
                )
        # Deduplicate by session_id + timestamp
        seen = set()
        unique = []
        for t in traces:
            key = (t.session_id, t.timestamp)
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique[:limit]

    def find_protocol_violations(self, limit: int = 10) -> list[FailureTrace]:
        """Find sessions where agent violated SOUL.md protocols.

        Patterns like:
        - Committed to hermes source (violates project_registry)
        - Claimed done without verification (violates reality_check)
        - Modified files in forbidden directories
        """
        traces = []
        for pattern in self.PROTOCOL_VIOLATION_PATTERNS:
            rows = self._query(
                """
                SELECT DISTINCT m.session_id, m.timestamp, m.content
                FROM messages m
                WHERE (m.role = 'user' OR m.role = 'assistant')
                AND m.content LIKE ?
                ORDER BY m.timestamp DESC
                LIMIT ?
                """,
                (pattern, limit),
            )
            for row in rows:
                traces.append(
                    FailureTrace(
                        session_id=row["session_id"],
                        timestamp=row["timestamp"],
                        what_happened=row["content"][:500],
                        user_correction="",
                        context="protocol_violation",
                    )
                )
        seen = set()
        unique = []
        for t in traces:
            key = (t.session_id, t.timestamp)
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique[:limit]

    def find_tool_failures(
        self, skill_name: str | None = None, limit: int = 10
    ) -> list[FailureTrace]:
        """Find sessions with repeated tool call failures.

        When a skill tells the agent to use tool X but it keeps failing,
        that's a signal the skill needs updating.
        """
        rows = self._query(
            """
            SELECT session_id, COUNT(*) as fail_count
            FROM messages
            WHERE role = 'tool'
            AND content LIKE '%error%' OR content LIKE '%Error%'
            GROUP BY session_id
            HAVING fail_count >= 3
            ORDER BY fail_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        traces = []
        for row in rows:
            # Get the first error from this session
            error = self._query(
                """
                SELECT content FROM messages
                WHERE session_id = ? AND role = 'tool'
                AND (content LIKE '%error%' OR content LIKE '%Error%')
                ORDER BY timestamp LIMIT 1
                """,
                (row["session_id"],),
            )
            traces.append(
                FailureTrace(
                    session_id=row["session_id"],
                    timestamp=0,
                    what_happened=f"{row['fail_count']} tool failures",
                    user_correction=error[0]["content"][:300] if error else "",
                    skill_name=skill_name or "",
                )
            )
        return traces

    def get_failure_summary(
        self, skill_name: str | None = None, limit: int = 5
    ) -> str:
        """Get a formatted failure summary for the reflector LLM.

        This is the Actionable Side Information — real traces from
        real usage that the reflector uses to improve the skill.
        """
        corrections = self.find_corrections(skill_name, limit)
        violations = self.find_protocol_violations(limit // 2)
        failures = self.find_tool_failures(skill_name, limit // 2)

        sections = []

        if corrections:
            sections.append("## USER CORRECTIONS (agent did X wrong)")
            for t in corrections:
                sections.append(
                    f"### Session {t.session_id}\n"
                    f"What agent did: {t.what_happened[:200]}\n"
                    f"User said: {t.user_correction[:200]}"
                )

        if violations:
            sections.append("## PROTOCOL VIOLATIONS")
            for t in violations:
                sections.append(
                    f"### Session {t.session_id}\n"
                    f"Violation: {t.what_happened[:300]}"
                )

        if failures:
            sections.append("## REPEATED TOOL FAILURES")
            for t in failures:
                sections.append(
                    f"### Session {t.session_id} ({t.what_happened})\n"
                    f"Error: {t.user_correction[:200]}"
                )

        if not sections:
            return "No failure traces found for this skill/SOUL.md."

        return "\n\n".join(sections)
