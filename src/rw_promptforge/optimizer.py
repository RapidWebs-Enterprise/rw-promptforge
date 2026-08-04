"""Optimizer — the core evaluate-reflect-improve loop.

Unlike a quality gate (which checks structural completeness), this optimizer
uses REAL failure traces from Hermes session_db to improve skills and SOUL.md.

Flow:
  1. Query session_db for real failures related to this artifact
  2. If failures found → feed to reflector → get improved version
  3. If no failures → artifact is already good (nothing to optimize)
  4. Repeat up to max_rounds, each time finding NEW failures
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from rw_promptforge.datastore.session_db import SessionDBReader
from rw_promptforge.reflector.engine import Reflector

MAX_ROUNDS_CAP = 20


@dataclass
class OptimizeResult:
    """Immutable optimization outcome."""

    artifact: str
    """The final (best) artifact text."""

    rounds: int
    """Number of reflection rounds executed."""

    failures_found: int
    """Total failure traces found and fed to the reflector."""

    converged: bool
    """True if no failures were found (nothing to improve)."""

    failure_summary: str
    """Summary of all failure traces used."""


class Optimizer:
    """Session-db driven evaluate → reflect → improve loop.

    For skills: finds real sessions where the skill was loaded and the agent failed.
    For SOUL.md: finds protocol violations the agent committed despite instructions.
    """

    def __init__(
        self,
        provider,  # Provider
        reflector: Reflector,
        max_rounds: int = 3,
        output_path: str | None = None,
        db_path: str | None = None,
    ) -> None:
        self.provider = provider
        self.reflector = reflector
        self.max_rounds = min(max_rounds, MAX_ROUNDS_CAP)
        self.output_path = Path(output_path) if output_path else None
        self.db = SessionDBReader(db_path)

    def optimize_skill(self, artifact_path: str, skill_name: str) -> OptimizeResult:
        """Optimize a skill file using real session_db failure traces."""
        artifact = Path(artifact_path).read_text()
        history = []
        total_failures = 0

        for round_num in range(self.max_rounds):
            # Query for real failures
            failure_summary = self.db.get_failure_summary(skill_name, limit=5)

            if "No relevant traces found" in failure_summary or "No failure traces found" in failure_summary:
                return OptimizeResult(
                    artifact=artifact,
                    rounds=round_num,
                    failures_found=total_failures,
                    converged=True,
                    failure_summary="No relevant failures found in session history.",
                )

            # Count failures
            failure_count = failure_summary.count("### Session")
            total_failures += failure_count

            # Reflect on real failures
            history_text = "\n".join(history) if history else "(first iteration)"
            artifact = self.reflector.reflect(
                artifact=artifact,
                failure_traces=failure_summary,
                history=history_text,
            )

            # Guard: reject empty/suspicious output
            if not artifact or len(artifact.strip()) < 10:
                break

            history.append(f"Round {round_num + 1}: fixed {failure_count} failures")

        # Save output if configured
        if self.output_path and artifact:
            self.output_path.write_text(artifact)

        return OptimizeResult(
            artifact=artifact,
            rounds=self.max_rounds,
            failures_found=total_failures,
            converged=False,
            failure_summary="\n".join(history),
        )

    def optimize_soul(self, artifact_path: str) -> OptimizeResult:
        """Optimize SOUL.md using real protocol violation traces."""
        artifact = Path(artifact_path).read_text()
        history = []
        total_failures = 0

        for round_num in range(self.max_rounds):
            # Query for protocol violations
            violations = self.db.find_protocol_violations(limit=10)
            corrections = self.db.find_corrections(limit=5)

            if not violations and not corrections:
                return OptimizeResult(
                    artifact=artifact,
                    rounds=round_num,
                    failures_found=total_failures,
                    converged=True,
                    failure_summary="No protocol violations or corrections found.",
                )

            # Build failure summary for SOUL.md
            sections = []
            if violations:
                sections.append("## PROTOCOL VIOLATIONS")
                for v in violations:
                    sections.append(
                        f"### Violation in session {v.session_id}\n"
                        f"{v.what_happened[:400]}"
                    )
            if corrections:
                sections.append("## USER CORRECTIONS")
                for c in corrections:
                    sections.append(
                        f"### Correction in session {c.session_id}\n"
                        f"What agent did: {c.what_happened[:200]}\n"
                        f"User said: {c.user_correction[:200]}"
                    )

            failure_summary = "\n\n".join(sections)
            failure_count = len(violations) + len(corrections)
            total_failures += failure_count

            # Reflect
            history_text = "\n".join(history) if history else "(first iteration)"
            artifact = self.reflector.reflect(
                artifact=artifact,
                failure_traces=failure_summary,
                history=history_text,
            )

            if not artifact or len(artifact.strip()) < 10:
                break

            history.append(f"Round {round_num + 1}: addressed {failure_count} violations")

        if self.output_path and artifact:
            self.output_path.write_text(artifact)

        return OptimizeResult(
            artifact=artifact,
            rounds=self.max_rounds,
            failures_found=total_failures,
            converged=False,
            failure_summary="\n".join(history),
        )
