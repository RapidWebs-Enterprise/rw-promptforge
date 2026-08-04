"""Session database reader — extracts real failure traces for optimization.

The key insight: instead of asking "does this file have the right sections?",
we ask "did this skill/SOUL.md prevent the agent from failing in real usage?"

Queries state.db for:
- Sessions where user corrected the agent after loading a skill
- Tool call failures when a skill was loaded
- Protocol violations (agent did X despite SOUL.md saying don't do X)
- Nearby successes (what the agent did RIGHT in the same session)
- Severity-ranked traces (HIGH > MEDIUM > LOW)
- Weighted failure type sampling
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rw_promptforge.datastore.models import (
    DEFAULT_FAILURE_TYPE_WEIGHTS,
    SEVERITY_LABELS,
    ContrastiveTraces,
    FailureTrace,
    LearningLogEntry,
)


class SessionDBReader:
    """Read Hermes session_db for real failure traces."""

    DEFAULT_PATH = Path.home() / ".hermes" / "state.db"

    CORRECTION_PATTERNS = [
        ("%thats not what%", 2, "general"),
        ("%that's not what%", 2, "general"),
        ("%not what i%", 2, "general"),
        ("%you were supposed%", 2, "general"),
        ("%you should have%", 2, "general"),
        ("%you did%wrong%", 2, "general"),
        ("%actually%should%", 1, "general"),
        ("%no, %", 1, "general"),
        ("%wrong%", 1, "general"),
        ("%you just%", 1, "general"),
        ("%you committed%", 2, "general"),
        ("%you were supposed to%", 2, "general"),
        ("%dont%commit%", 2, "general"),
        ("%don't%commit%", 2, "general"),
        ("%never%touch%", 2, "general"),
    ]
    # (pattern, severity, failure_type)

    PROTOCOL_VIOLATION_PATTERNS = [
        "%committed to hermes%",
        "%committed in hermes%",
        "%modified hermes source%",
        "%touched nousresearch%",
        "%skipped verification%",
        "%claimed done%",
        "%without verifying%",
    ]

    SUCCESS_PATTERNS = [
        "%correctly identified%",
        "%properly verified%",
        "%checked first%",
        "%asked the user%",
        "%confirmed before%",
        "%good work%",
        "%that's right%",
        "%exactly%",
    ]

    def __init__(
        self,
        db_path: str | Path | None = None,
        failure_type_weights: dict[str, float] | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_PATH
        self.failure_type_weights = failure_type_weights or DEFAULT_FAILURE_TYPE_WEIGHTS

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
        """Find sessions where user corrected the agent."""
        traces = []
        for pattern, severity, failure_type in self.CORRECTION_PATTERNS:
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
                        severity=severity,
                        failure_type=failure_type,
                    )
                )
        # Deduplicate and sort by severity
        seen = set()
        unique = []
        for t in traces:
            key = (t.session_id, t.timestamp)
            if key not in seen:
                seen.add(key)
                unique.append(t)
        unique.sort(key=lambda x: x.severity, reverse=True)
        return unique[:limit]

    def find_protocol_violations(self, limit: int = 10) -> list[FailureTrace]:
        """Find sessions where agent violated SOUL.md protocols."""
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
                        severity=2,
                        failure_type="protocol_violation",
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
        """Find sessions with repeated tool call failures."""
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
                    severity=1,
                    failure_type="tool_failure",
                )
            )
        return traces

    def find_successes(self, limit: int = 5) -> list[str]:
        """Find sessions where the agent did something right."""
        successes = []
        for pattern in self.SUCCESS_PATTERNS:
            rows = self._query(
                """
                SELECT content FROM messages
                WHERE role = 'user'
                AND content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (pattern, limit),
            )
            for row in rows:
                successes.append(row["content"][:200])
        return list(dict.fromkeys(successes))[:limit]

    def sample_failure_cases(
        self, traces: list[FailureTrace], weight_key: str = "severity"
    ) -> list[FailureTrace]:
        """Sample failure cases using weighted sampling.

        Modeled after Darwinian Evolver's weighted failure case sampling.
        """
        if not traces:
            return []

        # Group by failure_type and apply weights
        weighted_traces = []
        for t in traces:
            weight = self.failure_type_weights.get(t.failure_type, 1.0)
            # Create weighted copies for sampling
            for _ in range(max(1, int(weight * 10))):
                weighted_traces.append(t)

        # Sample proportional to weight
        import random

        sampled = random.sample(weighted_traces, min(len(traces), len(weighted_traces)))
        return sampled[:len(traces)]

    def get_contrastive_summary(
        self, skill_name: str | None = None, limit: int = 5
    ) -> ContrastiveTraces:
        """Get contrastive traces: failures + successes + root cause."""
        corrections = self.find_corrections(skill_name, limit)
        violations = self.find_protocol_violations(limit // 2)
        failures = self.find_tool_failures(skill_name, limit // 2)

        all_failures = corrections + violations + failures
        all_failures.sort(key=lambda x: x.severity, reverse=True)

        # Apply weighted sampling
        sampled_failures = self.sample_failure_cases(all_failures)

        successes = self.find_successes(limit)

        return ContrastiveTraces(
            failures=sampled_failures[:limit],
            successes=successes,
        )

    def format_contrastive_traces(self, traces: ContrastiveTraces) -> str:
        """Format contrastive traces for the reflector LLM."""
        sections = []

        if traces.failures:
            sections.append("## FAILURES (what went wrong)")
            for t in traces.failures:
                severity_label = SEVERITY_LABELS[t.severity]
                sections.append(
                    f"### [{severity_label}] Session {t.session_id}\n"
                    f"Type: {t.failure_type}\n"
                    f"What agent did: {t.what_happened[:200]}\n"
                    f"User said: {t.user_correction[:200] if t.user_correction else t.context}"
                )

        if traces.successes:
            sections.append("## SUCCESSES (what worked — preserve these)")
            for s in traces.successes:
                sections.append(f"- {s[:200]}")

        if traces.root_cause:
            sections.append(f"## ROOT CAUSE DIAGNOSIS\n{traces.root_cause}")

        if traces.learning_log:
            sections.append("## LEARNING LOG (past improvements)")
            for entry in traces.learning_log[-3:]:  # Last 3 entries
                sections.append(
                    f"- {entry.attempted_change}: {entry.observed_outcome}"
                )

        if not sections:
            return "No relevant traces found."

        return "\n\n".join(sections)

    def get_failure_summary(
        self, skill_name: str | None = None, limit: int = 5
    ) -> str:
        """Get a formatted failure summary for the reflector LLM."""
        traces = self.get_contrastive_summary(skill_name, limit)
        return self.format_contrastive_traces(traces)
